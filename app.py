from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response
import anthropic
import json
import os
import uuid
from datetime import datetime, date, timedelta
from pregnancy_data import PREGNANCY_WEEKS, WEEK_FRUIT_WIKI

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'pregnancy-lotus-secret-2026')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

COOKIE_NAME = 'pt_device_id'
COOKIE_MAX_AGE = 365 * 24 * 3600


def load_user(device_id):
    if not device_id:
        return None
    path = os.path.join(DATA_DIR, f'{device_id}.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_user(device_id, data):
    path = os.path.join(DATA_DIR, f'{device_id}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_device_id():
    return request.cookies.get(COOKIE_NAME, '')


def get_current_week(user_data):
    due = datetime.strptime(user_data['due_date'], '%Y-%m-%d').date()
    days_until_due = (due - date.today()).days
    week = 40 - round(days_until_due / 7)
    return max(1, min(40, week))


def get_due_date(user_data):
    return datetime.strptime(user_data['due_date'], '%Y-%m-%d').date()


def get_user_context():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return None, None, None, None
    current_week = get_current_week(user)
    due_date = get_due_date(user)
    return user, current_week, due_date, device_id


@app.route('/')
def index():
    device_id = get_device_id()
    if device_id and load_user(device_id):
        return redirect(url_for('dashboard'))
    return redirect(url_for('setup'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()
        due_date_str = request.form.get('due_date', '').strip()
        baby_gender = request.form.get('baby_gender', 'unknown')

        if not display_name or not due_date_str:
            return render_template('setup.html', error='יש למלא שם ותאריך לידה משוער')

        try:
            datetime.strptime(due_date_str, '%Y-%m-%d')
        except ValueError:
            return render_template('setup.html', error='תאריך לא תקין')

        if baby_gender not in ('boy', 'girl', 'unknown'):
            baby_gender = 'unknown'

        device_id = get_device_id()
        if not device_id:
            device_id = uuid.uuid4().hex

        existing = load_user(device_id) or {}
        existing.update({
            'display_name': display_name,
            'due_date': due_date_str,
            'baby_gender': baby_gender,
        })
        save_user(device_id, existing)

        resp = make_response(redirect(url_for('dashboard')))
        resp.set_cookie(COOKIE_NAME, device_id, max_age=COOKIE_MAX_AGE, samesite='Lax')
        return resp

    device_id = get_device_id()
    existing = load_user(device_id) if device_id else None
    return render_template('setup.html', existing=existing)


# Keep old login/register URLs working (redirect to setup)
@app.route('/login')
def login():
    return redirect(url_for('setup'))


@app.route('/register')
def register():
    return redirect(url_for('setup'))


@app.route('/dashboard')
def dashboard():
    user, current_week, due_date, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))

    days_left = (due_date - date.today()).days
    week_data = PREGNANCY_WEEKS.get(current_week, PREGNANCY_WEEKS[40])
    next_week = min(current_week + 1, 40)
    next_week_data = PREGNANCY_WEEKS.get(next_week)
    trimester = 1 if current_week <= 13 else (2 if current_week <= 27 else 3)
    progress = round((current_week / 40) * 100)

    return render_template('dashboard.html',
        user=user, current_week=current_week, due_date=due_date,
        days_left=days_left, week_data=week_data, next_week=next_week,
        next_week_data=next_week_data, trimester=trimester, progress=progress)


@app.route('/journey')
def journey():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    return render_template('journey.html', user=user, current_week=current_week, weeks=PREGNANCY_WEEKS)


@app.route('/week/<int:week_num>')
def week_detail(week_num):
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    if week_num < 1 or week_num > 40:
        return redirect(url_for('journey'))
    week_data = PREGNANCY_WEEKS.get(week_num)
    return render_template('week_detail.html', user=user, week_num=week_num,
                           week_data=week_data, current_week=current_week)


@app.route('/gallery')
def gallery():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    return render_template('gallery.html', user=user, current_week=current_week)


@app.route('/api/chat', methods=['POST'])
def chat():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401

    data = request.json or {}
    messages = data.get('messages', [])
    if not messages:
        return jsonify({'error': 'אין הודעות'}), 400

    current_week = get_current_week(user)
    due_date = get_due_date(user)
    days_left = (due_date - date.today()).days
    trimester = 1 if current_week <= 13 else (2 if current_week <= 27 else 3)
    week_data = PREGNANCY_WEEKS.get(current_week, PREGNANCY_WEEKS[40])

    gender_map = {'boy': 'בן', 'girl': 'בת', 'unknown': 'עדיין לא ידוע'}
    baby_gender_display = gender_map.get(user.get('baby_gender', 'unknown'), 'עדיין לא ידוע')

    system = f"""את רחלי 🌸 — מלווה הריון חמה ומקצועית, ומלווה את {user['display_name']} במסע ההריון שלה.

## מי את
אני רחלי — מלווה הריון עם ניסיון רב בליווי נשים לאורך כל שלבי ההיריון. אני מבינה לעומק את מה ש{user['display_name']} עוברת — מהרגשות, דרך הפיזי, ועד לכל השאלות הקטנות שמתעוררות בדרך.
אני כאן לחלוק ידע, לתת עצות מעשיות שעובדות, ולהיות נוכחת לצדה בכל שלב.

## המצב של {user['display_name']}
- שבוע הריון: {current_week} מתוך 40
- טרימסטר: {trimester}
- מועד לידה צפוי: {due_date.strftime('%d.%m.%Y')}
- ימים עד הלידה: {days_left}
- מין התינוק: {baby_gender_display}
- גודל התינוק השבוע: {week_data['size']} ({week_data['length']}, {week_data['weight']})

## התפתחות השבוע
{'; '.join(week_data['development'][:3])}

## כיצד אני מדברת
- עברית בלבד
- בגוף ראשון נקבה — "אני", "שלי", "אצלי"
- חמה, תומכת ונוכחת — כמו חברה מנוסה שמבינה הכל
- תשובות קצרות וישירות — 2-4 משפטים
- לא מתחילה ב"בהחלט", "כמובן", "שאלה מצוינת"
- מדויקת רפואית אבל לא מפחידה
- לשאלות רפואיות דחופות — תמיד מפנה לרופא/מיילדת"""

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return jsonify({'error': 'מפתח API לא מוגדר בשרת'}), 500

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=600,
            system=system,
            messages=messages
        )
        reply = response.content[0].text
        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Journal ────────────────────────────────────────────────────────────────

@app.route('/journal')
def journal():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    entries = sorted(user.get('journal', []), key=lambda e: e['week'], reverse=True)
    return render_template('journal.html', user=user, current_week=current_week, entries=entries)


@app.route('/api/journal', methods=['POST'])
def save_journal_entry():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    data = request.json or {}
    week = data.get('week')
    text = data.get('text', '').strip()
    entry_id = data.get('id')
    if not text or not week:
        return jsonify({'error': 'חסר מידע'}), 400

    entries = user.setdefault('journal', [])
    if entry_id:
        for e in entries:
            if e['id'] == entry_id:
                e['text'] = text
                e['updated_at'] = datetime.now().strftime('%d.%m.%Y')
                break
    else:
        entries.append({
            'id': uuid.uuid4().hex[:10],
            'week': int(week),
            'text': text,
            'created_at': datetime.now().strftime('%d.%m.%Y %H:%M'),
            'updated_at': None
        })
    save_user(device_id, user)
    return jsonify({'success': True})


@app.route('/api/journal/<entry_id>', methods=['DELETE'])
def delete_journal_entry(entry_id):
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    user['journal'] = [e for e in user.get('journal', []) if e['id'] != entry_id]
    save_user(device_id, user)
    return jsonify({'success': True})


# ─── Appointments ────────────────────────────────────────────────────────────

@app.route('/appointments')
def appointments():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    appts = sorted(user.get('appointments', []), key=lambda a: a['date'])
    today = date.today().isoformat()
    upcoming = [a for a in appts if a['date'] >= today]
    past = [a for a in appts if a['date'] < today]
    return render_template('appointments.html', user=user, current_week=current_week,
                           upcoming=upcoming, past=past, today=today)


@app.route('/api/appointments', methods=['POST'])
def save_appointment():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    data = request.json or {}
    appt_date = data.get('date', '').strip()
    appt_type = data.get('type', '').strip()
    notes = data.get('notes', '').strip()
    if not appt_date or not appt_type:
        return jsonify({'error': 'חסר מידע'}), 400
    user.setdefault('appointments', []).append({
        'id': uuid.uuid4().hex[:10],
        'date': appt_date,
        'type': appt_type,
        'notes': notes,
        'created_at': datetime.now().strftime('%d.%m.%Y')
    })
    save_user(device_id, user)
    return jsonify({'success': True})


@app.route('/api/appointments/<appt_id>', methods=['DELETE'])
def delete_appointment(appt_id):
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    user['appointments'] = [a for a in user.get('appointments', []) if a['id'] != appt_id]
    save_user(device_id, user)
    return jsonify({'success': True})


# ─── Baby Names ──────────────────────────────────────────────────────────────

@app.route('/names')
def names():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    return render_template('names.html', user=user, current_week=current_week,
                           names=user.get('baby_names', []))


@app.route('/api/names', methods=['POST'])
def add_name():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    data = request.json or {}
    name = data.get('name', '').strip()
    gender = data.get('gender', 'unknown')
    if not name:
        return jsonify({'error': 'חסר שם'}), 400
    baby_names = user.setdefault('baby_names', [])
    if any(n['name'] == name for n in baby_names):
        return jsonify({'error': 'השם כבר קיים ברשימה'}), 400
    baby_names.append({'id': uuid.uuid4().hex[:10], 'name': name, 'gender': gender, 'liked': False})
    save_user(device_id, user)
    return jsonify({'success': True})


@app.route('/api/names/<name_id>/like', methods=['POST'])
def toggle_name_like(name_id):
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    for n in user.get('baby_names', []):
        if n['id'] == name_id:
            n['liked'] = not n['liked']
            break
    save_user(device_id, user)
    return jsonify({'success': True})


@app.route('/api/names/<name_id>', methods=['DELETE'])
def delete_name(name_id):
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    user['baby_names'] = [n for n in user.get('baby_names', []) if n['id'] != name_id]
    save_user(device_id, user)
    return jsonify({'success': True})


MOOD_OPTIONS = [
    {'key': 'great',     'emoji': '😊', 'label': 'מעולה'},
    {'key': 'tired',     'emoji': '😴', 'label': 'עייפה'},
    {'key': 'emotional', 'emoji': '💜', 'label': 'רגשית'},
    {'key': 'irritable', 'emoji': '😤', 'label': 'עצבנית'},
    {'key': 'strong',    'emoji': '💪', 'label': 'חזקה'},
]

BIRTH_CHECKLIST = [
    {'cat': 'לתינוק 👶', 'items': [
        'תלבושות ראשוניות (5-6 ערכות)',
        'שמיכות וחיתולי בד',
        'חיתולים מגנים',
        'כובעון רך',
        'גרביים קטנות',
        'מוצץ',
        'מטפחות לחות ויבשות',
    ]},
    {'cat': 'לאמא 💕', 'items': [
        'כותונת לידה נוחה',
        'חזיות הנקה (2-3)',
        'תחתוניות גדולות (5-6)',
        'רובה נוחה ונעלי בית',
        'תחבושות אחרי לידה',
        'קרם/שמן לבטן',
        'כרית הנקה',
    ]},
    {'cat': 'ניירת 📄', 'items': [
        'תעודת זהות',
        'ספר הריון מלא',
        'טופס ביטוח לאומי',
        'מספר חדר הלידה שמור',
        'תוכנית לידה (אם יש)',
    ]},
    {'cat': 'נוחות ✨', 'items': [
        'אוזניות + מוזיקה מרגיעה',
        'מטען לטלפון + כבל',
        'חטיפים קלים לבן הזוג',
        'שמפו, סבון, דאודורנט',
        'מברשת שיניים ומשחה',
        'מראה קטנה',
    ]},
]


# ─── Kick Counter ─────────────────────────────────────────────────────────────

@app.route('/kicks')
def kicks():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    return render_template('kicks.html', user=user, current_week=current_week)


@app.route('/api/kicks', methods=['GET', 'POST'])
def kicks_api():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401

    if request.method == 'POST':
        today = date.today().isoformat()
        kicks_data = user.setdefault('kicks', {})
        kicks_data[today] = kicks_data.get(today, 0) + 1
        save_user(device_id, user)
        return jsonify({'count': kicks_data[today]})

    kicks_data = user.get('kicks', {})
    today = date.today().isoformat()
    days = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        days.append({'date': d, 'count': kicks_data.get(d, 0)})
    return jsonify({'today': kicks_data.get(today, 0), 'days': days})


@app.route('/api/kicks/reset', methods=['POST'])
def reset_kicks():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    today = date.today().isoformat()
    user.setdefault('kicks', {})[today] = 0
    save_user(device_id, user)
    return jsonify({'count': 0})


# ─── Mood Tracker ─────────────────────────────────────────────────────────────

@app.route('/mood')
def mood():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    today_mood = user.get('moods', {}).get(date.today().isoformat())
    return render_template('mood.html', user=user, current_week=current_week,
                           today_mood=today_mood, mood_options=MOOD_OPTIONS)


@app.route('/api/mood', methods=['POST'])
def save_mood():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    data = request.json or {}
    mood_key = data.get('mood_key', '')
    note = data.get('note', '').strip()
    opt = next((m for m in MOOD_OPTIONS if m['key'] == mood_key), None)
    if not opt:
        return jsonify({'error': 'מצב רוח לא תקין'}), 400
    today = date.today().isoformat()
    user.setdefault('moods', {})[today] = {
        'key': mood_key, 'emoji': opt['emoji'], 'label': opt['label'], 'note': note,
    }
    save_user(device_id, user)
    return jsonify({'success': True})


@app.route('/api/mood/history')
def mood_history():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    moods_data = user.get('moods', {})
    days = []
    for i in range(13, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        days.append({'date': d, 'mood': moods_data.get(d)})
    return jsonify({'days': days})


# ─── Birth Checklist ──────────────────────────────────────────────────────────

@app.route('/checklist')
def checklist():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    checked = user.get('checklist', {})
    items_list = []
    for cat_idx, cat in enumerate(BIRTH_CHECKLIST):
        entries = []
        for item_idx, text in enumerate(cat['items']):
            key = f'item_{cat_idx}_{item_idx}'
            entries.append({'text': text, 'key': key, 'checked': checked.get(key, False)})
        items_list.append({'cat': cat['cat'], 'entries': entries})
    total = sum(len(c['items']) for c in BIRTH_CHECKLIST)
    done = sum(1 for v in checked.values() if v)
    circumference = round(2 * 3.14159265 * 66, 2)
    offset = round(circumference * (1 - done / total), 2) if total > 0 else circumference
    return render_template('checklist.html', user=user, current_week=current_week,
                           checklist=items_list, total=total, done=done,
                           circumference=circumference, offset=offset)


@app.route('/api/checklist', methods=['POST'])
def toggle_checklist():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    data = request.json or {}
    key = data.get('key', '')
    if not key:
        return jsonify({'error': 'חסר מפתח'}), 400
    cl = user.setdefault('checklist', {})
    cl[key] = not cl.get(key, False)
    save_user(device_id, user)
    total = sum(len(c['items']) for c in BIRTH_CHECKLIST)
    done = sum(1 for v in cl.values() if v)
    return jsonify({'checked': cl[key], 'done': done, 'total': total})


# ─── Belly Measurements ───────────────────────────────────────────────────────

@app.route('/measurements')
def measurements():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    ms = sorted(user.get('measurements', []), key=lambda m: m['week'])
    return render_template('measurements.html', user=user, current_week=current_week, measurements=ms)


@app.route('/api/measurements', methods=['POST'])
def add_measurement():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    data = request.json or {}
    try:
        week = int(data.get('week', 0))
        cm = float(data.get('cm', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'ערכים לא תקינים'}), 400
    if week < 1 or week > 40 or cm < 10 or cm > 200:
        return jsonify({'error': 'ערכים לא תקינים'}), 400
    user.setdefault('measurements', []).append({
        'id': uuid.uuid4().hex[:10], 'week': week, 'cm': cm,
        'date': date.today().isoformat(),
    })
    save_user(device_id, user)
    return jsonify({'success': True})


@app.route('/api/measurements/<m_id>', methods=['DELETE'])
def delete_measurement(m_id):
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    user['measurements'] = [m for m in user.get('measurements', []) if m['id'] != m_id]
    save_user(device_id, user)
    return jsonify({'success': True})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=True)
