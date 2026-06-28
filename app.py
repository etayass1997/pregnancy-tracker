from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response, send_from_directory
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


# ─── Weight Tracker ───────────────────────────────────────────────────────────

@app.route('/weight')
def weight():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    weights = sorted(user.get('weight', []), key=lambda w: w['week'])
    return render_template('weight.html', user=user, current_week=current_week, weights=weights)


@app.route('/api/weight', methods=['POST'])
def add_weight():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    data = request.json or {}
    try:
        week = int(data.get('week', 0))
        kg = float(data.get('kg', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'ערכים לא תקינים'}), 400
    if week < 1 or week > 40 or kg < 30 or kg > 200:
        return jsonify({'error': 'ערכים לא תקינים'}), 400
    user.setdefault('weight', []).append({
        'id': uuid.uuid4().hex[:10], 'week': week, 'kg': kg,
        'date': date.today().isoformat(),
    })
    save_user(device_id, user)
    return jsonify({'success': True})


@app.route('/api/weight/<w_id>', methods=['DELETE'])
def delete_weight(w_id):
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    user['weight'] = [w for w in user.get('weight', []) if w['id'] != w_id]
    save_user(device_id, user)
    return jsonify({'success': True})


# ─── Blood Pressure Tracker ───────────────────────────────────────────────────

@app.route('/bp')
def bp():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    readings = sorted(user.get('bp', []), key=lambda r: r['date'], reverse=True)
    return render_template('bp.html', user=user, current_week=current_week, readings=readings)


@app.route('/api/bp', methods=['POST'])
def add_bp():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    data = request.json or {}
    try:
        systolic = int(data.get('systolic', 0))
        diastolic = int(data.get('diastolic', 0))
        pulse = int(data.get('pulse')) if data.get('pulse') else None
    except (ValueError, TypeError):
        return jsonify({'error': 'ערכים לא תקינים'}), 400
    if systolic < 70 or systolic > 200 or diastolic < 40 or diastolic > 130:
        return jsonify({'error': 'ערכים לא תקינים'}), 400
    current_week = get_current_week(user)
    user.setdefault('bp', []).append({
        'id': uuid.uuid4().hex[:10], 'systolic': systolic, 'diastolic': diastolic,
        'pulse': pulse, 'week': current_week, 'date': date.today().isoformat(),
        'time': datetime.now().strftime('%H:%M'),
    })
    save_user(device_id, user)
    return jsonify({'success': True})


@app.route('/api/bp/<bp_id>', methods=['DELETE'])
def delete_bp(bp_id):
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    user['bp'] = [r for r in user.get('bp', []) if r['id'] != bp_id]
    save_user(device_id, user)
    return jsonify({'success': True})


# ─── Symptoms Log ─────────────────────────────────────────────────────────────

SYMPTOM_OPTIONS = [
    {'key': 'nausea',             'emoji': '🤢', 'label': 'בחילה'},
    {'key': 'heartburn',          'emoji': '🔥', 'label': 'צרבת'},
    {'key': 'back_pain',          'emoji': '🦴', 'label': 'כאב גב'},
    {'key': 'fatigue',            'emoji': '😴', 'label': 'עייפות'},
    {'key': 'swelling',           'emoji': '💧', 'label': 'נפיחות'},
    {'key': 'headache',           'emoji': '🤕', 'label': 'כאב ראש'},
    {'key': 'cramps',             'emoji': '⚡', 'label': 'כאבי בטן'},
    {'key': 'shortness_breath',   'emoji': '💨', 'label': 'קוצר נשימה'},
    {'key': 'insomnia',           'emoji': '🌙', 'label': 'נדודי שינה'},
    {'key': 'mood_swings',        'emoji': '💜', 'label': 'שינויי מצב רוח'},
    {'key': 'frequent_urination', 'emoji': '🚽', 'label': 'תכיפות שתן'},
    {'key': 'contractions_bh',    'emoji': '⏰', 'label': 'צירי בראקסטון'},
]


@app.route('/symptoms')
def symptoms():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    today_iso = date.today().isoformat()
    today_symptoms = user.get('symptoms', {}).get(today_iso, {})
    history = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        s = user.get('symptoms', {}).get(d, {})
        history.append({'date': d, 'syms': s.get('items', []), 'note': s.get('note', '')})
    return render_template('symptoms.html', user=user, current_week=current_week,
                           today_symptoms=today_symptoms, symptom_options=SYMPTOM_OPTIONS,
                           history=history)


@app.route('/api/symptoms', methods=['POST'])
def save_symptoms():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    data = request.json or {}
    items = data.get('items', [])
    note = data.get('note', '').strip()
    today = date.today().isoformat()
    current_week = get_current_week(user)
    user.setdefault('symptoms', {})[today] = {'items': items, 'note': note, 'week': current_week}
    save_user(device_id, user)
    return jsonify({'success': True})


# ─── Doctor Questions ─────────────────────────────────────────────────────────

@app.route('/questions')
def questions():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    qs = user.get('doctor_questions', [])
    pending = [q for q in qs if not q.get('answered')]
    answered = [q for q in qs if q.get('answered')]
    return render_template('questions.html', user=user, current_week=current_week,
                           pending=pending, answered=answered)


@app.route('/api/questions', methods=['POST'])
def add_question():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    data = request.json or {}
    question = data.get('question', '').strip()
    if not question:
        return jsonify({'error': 'חסרה שאלה'}), 400
    user.setdefault('doctor_questions', []).append({
        'id': uuid.uuid4().hex[:10], 'question': question,
        'answered': False, 'created_at': datetime.now().strftime('%d.%m.%Y'),
    })
    save_user(device_id, user)
    return jsonify({'success': True})


@app.route('/api/questions/<q_id>/answer', methods=['POST'])
def answer_question(q_id):
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    for q in user.get('doctor_questions', []):
        if q['id'] == q_id:
            q['answered'] = not q['answered']
            break
    save_user(device_id, user)
    return jsonify({'success': True})


@app.route('/api/questions/<q_id>', methods=['DELETE'])
def delete_question(q_id):
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    user['doctor_questions'] = [q for q in user.get('doctor_questions', []) if q['id'] != q_id]
    save_user(device_id, user)
    return jsonify({'success': True})


# ─── Birth Plan ───────────────────────────────────────────────────────────────

BIRTH_PLAN_SECTIONS = [
    {'key': 'pain_relief', 'title': 'שיכוך כאב 💊', 'options': [
        {'key': 'epidural', 'label': 'אפידורל'},
        {'key': 'natural', 'label': 'לידה טבעית ללא כאב'},
        {'key': 'gas', 'label': 'גז צחוק (N₂O)'},
        {'key': 'pool', 'label': 'אמבט לידה'},
        {'key': 'massage', 'label': 'עיסוי ונשימות'},
    ]},
    {'key': 'environment', 'title': 'סביבת הלידה 🕯️', 'options': [
        {'key': 'dim_lights', 'label': 'תאורה עמומה'},
        {'key': 'music', 'label': 'מוזיקה מרגיעה'},
        {'key': 'quiet', 'label': 'שקט מקסימלי'},
        {'key': 'partner_present', 'label': 'בן/בת זוג נוכח/ת'},
        {'key': 'photographer', 'label': 'צלמת לידה'},
    ]},
    {'key': 'after_birth', 'title': 'אחרי הלידה 🍼', 'options': [
        {'key': 'skin_to_skin', 'label': 'מגע עור לעור מיידי'},
        {'key': 'delayed_cord', 'label': 'עיכוב חיתוך חבל הטבור'},
        {'key': 'partner_cuts', 'label': 'בן/בת זוג חותך/ת חבל'},
        {'key': 'breastfeed', 'label': 'הנקה מיידית'},
        {'key': 'no_formula', 'label': 'ללא פורמולה בלי הסכמה'},
    ]},
    {'key': 'interventions', 'title': 'התערבויות רפואיות 🏥', 'options': [
        {'key': 'no_episiotomy', 'label': 'הימנעות מאפיזיוטומיה'},
        {'key': 'minimize', 'label': 'מינימום התערבויות'},
        {'key': 'continuous_monitor', 'label': 'מוניטור רציף'},
        {'key': 'iv_if_needed', 'label': 'עירוי רק במידת הצורך'},
    ]},
]


@app.route('/birthplan')
def birthplan():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    plan = user.get('birth_plan', {})
    return render_template('birthplan.html', user=user, current_week=current_week,
                           plan=plan, sections=BIRTH_PLAN_SECTIONS)


@app.route('/api/birthplan', methods=['POST'])
def save_birthplan():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    data = request.json or {}
    plan = {}
    for sec in BIRTH_PLAN_SECTIONS:
        plan[sec['key']] = data.get(sec['key'], [])
    plan['custom_notes'] = data.get('custom_notes', '').strip()
    user['birth_plan'] = plan
    save_user(device_id, user)
    return jsonify({'success': True})


# ─── Contraction Timer ────────────────────────────────────────────────────────

@app.route('/contractions')
def contractions():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    return render_template('contractions.html', user=user, current_week=current_week)


@app.route('/api/contractions', methods=['GET', 'POST', 'DELETE'])
def contractions_api():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401

    if request.method == 'DELETE':
        user['contractions_session'] = []
        save_user(device_id, user)
        return jsonify({'success': True})

    if request.method == 'POST':
        data = request.json or {}
        action = data.get('action')
        session = user.setdefault('contractions_session', [])

        if action == 'start':
            now_str = datetime.now().isoformat()
            entry = {'id': uuid.uuid4().hex[:10], 'start': now_str, 'end': None,
                     'duration': None, 'interval': None}
            if session:
                last = session[-1]
                if last.get('end'):
                    try:
                        last_end = datetime.fromisoformat(last['end'])
                        interval_sec = int((datetime.fromisoformat(now_str) - last_end).total_seconds())
                        entry['interval'] = interval_sec
                    except Exception:
                        pass
            session.append(entry)
            save_user(device_id, user)
            return jsonify({'success': True, 'id': entry['id']})

        elif action == 'stop':
            c_id = data.get('id')
            now_str = datetime.now().isoformat()
            for c in session:
                if c['id'] == c_id and not c['end']:
                    c['end'] = now_str
                    try:
                        duration = int((datetime.fromisoformat(now_str) - datetime.fromisoformat(c['start'])).total_seconds())
                        c['duration'] = duration
                    except Exception:
                        pass
                    break
            save_user(device_id, user)
            return jsonify({'success': True})

    session = user.get('contractions_session', [])
    return jsonify({'session': session})


# ─── Nutrition Guide ──────────────────────────────────────────────────────────

@app.route('/nutrition')
def nutrition():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    trimester = 1 if current_week <= 13 else (2 if current_week <= 27 else 3)
    return render_template('nutrition.html', user=user, current_week=current_week, trimester=trimester)


# ─── Achievements ─────────────────────────────────────────────────────────────

ALL_ACHIEVEMENTS = [
    {'id': 'week1',     'emoji': '🌱', 'title': 'ההתחלה',        'desc': 'ברוכה הבאה למסע!',                  'week': 1},
    {'id': 'heartbeat', 'emoji': '💓', 'title': 'לב פועם',        'desc': 'הלב של התינוק כבר פועם!',            'week': 6},
    {'id': 'trim2',     'emoji': '🌞', 'title': 'טרימסטר שני!',   'desc': 'סיימת את הטרימסטר הראשון!',          'week': 13},
    {'id': 'halfway',   'emoji': '🎉', 'title': 'חצי הדרך!',      'desc': 'שבוע 20 — אמצע ההריון!',             'week': 20},
    {'id': 'viable',    'emoji': '⭐', 'title': 'שבוע הכדאיות',   'desc': 'שבוע 24 — תינוק בר קיימא!',          'week': 24},
    {'id': 'trim3',     'emoji': '🌟', 'title': 'טרימסטר שלישי!', 'desc': 'הטרימסטר האחרון — כמעט שם!',         'week': 28},
    {'id': 'week30',    'emoji': '🏆', 'title': 'שבוע 30',         'desc': 'עוד רק 10 שבועות!',                  'week': 30},
    {'id': 'week35',    'emoji': '💎', 'title': 'כמעט מוכנה',      'desc': 'שבוע 35 — הישגה עצומה!',             'week': 35},
    {'id': 'fullterm',  'emoji': '👑', 'title': 'Full Term!',      'desc': 'שבוע 37 — תינוק בשל ומוכן!',         'week': 37},
    {'id': 'week40',    'emoji': '🌸', 'title': 'מועד הלידה',      'desc': 'הגעת לשבוע 40 — מדהים!',             'week': 40},
    {'id': 'journal5',  'emoji': '📓', 'title': 'כותבת יומן',      'desc': 'כתבת 5 רשומות ביומן',        'type': 'journal',     'count': 5},
    {'id': 'kicks50',   'emoji': '💪', 'title': 'ספרנית בעיטות',   'desc': 'רשמת 50 בעיטות — כל הכבוד!', 'type': 'kicks_total', 'count': 50},
]


@app.route('/achievements')
def achievements():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    journal_count = len(user.get('journal', []))
    kicks_total = int(sum(user.get('kicks', {}).values()))
    unlocked = set()
    for ach in ALL_ACHIEVEMENTS:
        if 'week' in ach and current_week >= ach['week']:
            unlocked.add(ach['id'])
        elif ach.get('type') == 'journal' and journal_count >= ach['count']:
            unlocked.add(ach['id'])
        elif ach.get('type') == 'kicks_total' and kicks_total >= ach['count']:
            unlocked.add(ach['id'])
    return render_template('achievements.html', user=user, current_week=current_week,
                           achievements=ALL_ACHIEVEMENTS, unlocked=unlocked,
                           journal_count=journal_count, kicks_total=kicks_total)


# ─── Exercise Guide ───────────────────────────────────────────────────────────

@app.route('/exercise')
def exercise():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    trimester = 1 if current_week <= 13 else (2 if current_week <= 27 else 3)
    return render_template('exercise.html', user=user, current_week=current_week, trimester=trimester)


# ─── Vitamin Tracker ──────────────────────────────────────────────────────────

VITAMIN_LIST = [
    {'key': 'folic',     'label': 'חומצה פולית', 'emoji': '🌿', 'note': '400–800 מק"ג ביום'},
    {'key': 'iron',      'label': 'ברזל',         'emoji': '🔴', 'note': 'לפי המלצת רופא'},
    {'key': 'd3',        'label': 'ויטמין D3',    'emoji': '☀️', 'note': '400–600 IU ביום'},
    {'key': 'calcium',   'label': 'סידן',          'emoji': '🥛', 'note': '1000 מג ביום'},
    {'key': 'omega3',    'label': 'אומגה 3',       'emoji': '🐟', 'note': 'DHA לפיתוח מוח התינוק'},
    {'key': 'b12',       'label': 'ויטמין B12',    'emoji': '💊', 'note': 'חשוב במיוחד לצמחוניות'},
    {'key': 'magnesium', 'label': 'מגנזיום',       'emoji': '✨', 'note': 'לקרמפים ולשינה טובה'},
]


@app.route('/vitamins')
def vitamins():
    user, current_week, _, _ = get_user_context()
    if not user:
        return redirect(url_for('setup'))
    today = date.today().isoformat()
    today_vitamins = user.get('vitamins', {}).get(today, {})
    history = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        v = user.get('vitamins', {}).get(d, {})
        count = sum(1 for vit in VITAMIN_LIST if v.get(vit['key']))
        history.append({'date': d, 'count': count, 'total': len(VITAMIN_LIST)})
    return render_template('vitamins.html', user=user, current_week=current_week,
                           today_vitamins=today_vitamins, vitamin_list=VITAMIN_LIST,
                           history=history)


@app.route('/api/vitamins', methods=['POST'])
def save_vitamins():
    device_id = get_device_id()
    user = load_user(device_id)
    if not user:
        return jsonify({'error': 'לא מוגדרת'}), 401
    data = request.json or {}
    key = data.get('key', '')
    today = date.today().isoformat()
    vits = user.setdefault('vitamins', {}).setdefault(today, {})
    vits[key] = not vits.get(key, False)
    save_user(device_id, user)
    return jsonify({'checked': vits[key]})


@app.route('/sw.js')
def service_worker():
    response = make_response(send_from_directory('static', 'sw.js'))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache'
    return response


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=True)
