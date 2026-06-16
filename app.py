from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import anthropic
import json
import os
import uuid
from datetime import datetime, date, timedelta
from pregnancy_data import PREGNANCY_WEEKS

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'pregnancy-lotus-secret-2026')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'users.json')

os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)


def load_users():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_users(users):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def get_current_week(user_data):
    reg_date = datetime.strptime(user_data['registration_date'], '%Y-%m-%d').date()
    reg_week = user_data['registration_week']
    weeks_elapsed = (date.today() - reg_date).days // 7
    return min(reg_week + weeks_elapsed, 40)


def get_due_date(user_data):
    reg_date = datetime.strptime(user_data['registration_date'], '%Y-%m-%d').date()
    weeks_remaining = 40 - user_data['registration_week']
    return reg_date + timedelta(weeks=weeks_remaining)


def get_user_context():
    if 'username' not in session:
        return None, None, None, None
    users = load_users()
    user = users.get(session['username'])
    if not user:
        return None, None, None, None
    current_week = get_current_week(user)
    due_date = get_due_date(user)
    return user, current_week, due_date, users


@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        users = load_users()
        if username in users and check_password_hash(users[username]['password_hash'], password):
            session['username'] = username
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='שם משתמש או סיסמה שגויים')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        display_name = request.form.get('display_name', '').strip()
        password = request.form.get('password', '')
        current_week = int(request.form.get('current_week', 1))
        baby_gender = request.form.get('baby_gender', 'unknown')
        if baby_gender not in ('boy', 'girl', 'unknown'):
            baby_gender = 'unknown'

        if not username or not password or not display_name:
            return render_template('register.html', error='יש למלא את כל השדות')
        if current_week < 1 or current_week > 40:
            return render_template('register.html', error='שבוע הריון חייב להיות בין 1 ל-40')

        users = load_users()
        if username in users:
            return render_template('register.html', error='שם משתמש כבר קיים, נסי שם אחר')

        users[username] = {
            'password_hash': generate_password_hash(password),
            'display_name': display_name,
            'registration_date': date.today().isoformat(),
            'registration_week': current_week,
            'baby_gender': baby_gender,
            'photos': []
        }
        save_users(users)
        session['username'] = username
        return redirect(url_for('dashboard'))
    return render_template('register.html')


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    user, current_week, due_date, _ = get_user_context()
    if not user:
        return redirect(url_for('login'))

    days_left = (due_date - date.today()).days
    week_data = PREGNANCY_WEEKS.get(current_week, PREGNANCY_WEEKS[40])
    next_week = min(current_week + 1, 40)
    next_week_data = PREGNANCY_WEEKS.get(next_week)
    trimester = 1 if current_week <= 13 else (2 if current_week <= 27 else 3)
    progress = round((current_week / 40) * 100)

    return render_template('dashboard.html',
        user=user,
        current_week=current_week,
        due_date=due_date,
        days_left=days_left,
        week_data=week_data,
        next_week=next_week,
        next_week_data=next_week_data,
        trimester=trimester,
        progress=progress
    )


@app.route('/journey')
def journey():
    if 'username' not in session:
        return redirect(url_for('login'))
    user, current_week, due_date, _ = get_user_context()
    if not user:
        return redirect(url_for('login'))

    return render_template('journey.html',
        user=user,
        current_week=current_week,
        weeks=PREGNANCY_WEEKS
    )


@app.route('/week/<int:week_num>')
def week_detail(week_num):
    if 'username' not in session:
        return redirect(url_for('login'))
    if week_num < 1 or week_num > 40:
        return redirect(url_for('journey'))

    user, current_week, due_date, _ = get_user_context()
    if not user:
        return redirect(url_for('login'))

    week_data = PREGNANCY_WEEKS.get(week_num)
    return render_template('week_detail.html',
        user=user,
        week_num=week_num,
        week_data=week_data,
        current_week=current_week
    )


@app.route('/gallery')
def gallery():
    if 'username' not in session:
        return redirect(url_for('login'))
    user, current_week, due_date, _ = get_user_context()
    if not user:
        return redirect(url_for('login'))
    return render_template('gallery.html', user=user, current_week=current_week)


@app.route('/api/chat', methods=['POST'])
def chat():
    if 'username' not in session:
        return jsonify({'error': 'לא מחוברת'}), 401

    data = request.json or {}
    messages = data.get('messages', [])
    if not messages:
        return jsonify({'error': 'אין הודעות'}), 400

    user, current_week, due_date, _ = get_user_context()
    if not user:
        return jsonify({'error': 'משתמשת לא נמצאה'}), 401

    days_left = (due_date - date.today()).days
    trimester = 1 if current_week <= 13 else (2 if current_week <= 27 else 3)
    week_data = PREGNANCY_WEEKS.get(current_week, PREGNANCY_WEEKS[40])

    gender_map = {'boy': 'בן', 'girl': 'בת', 'unknown': 'לא ידוע עדיין'}
    baby_gender_display = gender_map.get(user.get('baby_gender', 'unknown'), 'לא ידוע עדיין')

    system = f"""אתה "הריונית" 🌸 — הסוכנת האישית של {user['display_name']} באפליקציית מעקב הריון.

## מצב נוכחי
- שם: {user['display_name']}
- שבוע הריון: {current_week} מתוך 40
- טרימסטר: {trimester}
- מועד לידה צפוי: {due_date.strftime('%d.%m.%Y')}
- ימים עד הלידה: {days_left}
- מין התינוק: {baby_gender_display}
- גודל התינוק השבוע: {week_data['size']} ({week_data['length']}, {week_data['weight']})

## פרטי השבוע
התפתחות עיקרית: {'; '.join(week_data['development'][:2])}
תחושות שכיחות: {'; '.join(week_data['mom_feelings'][:2])}

## האפליקציה
ל-{user['display_name']} יש גישה ל:
- לוח בקרה (Dashboard) עם מידע על השבוע הנוכחי
- מסע שבועי — ציר זמן של כל 40 שבועות
- גלריה — לתעד תמונות מההריון, מאורגנות לפי שבוע
- הצ'אט איתך

## כללי תקשורת
- עברית בלבד
- סגנון חם, אמפתי, תומך — כמו חברה טובה שגם יודעת הכל על הריון
- פוני ב"את" (לאישה)
- תשובות קצרות — 2-4 משפטים בדרך כלל
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
    if 'username' not in session:
        return redirect(url_for('login'))
    user, current_week, due_date, _ = get_user_context()
    if not user:
        return redirect(url_for('login'))
    entries = sorted(user.get('journal', []), key=lambda e: e['week'], reverse=True)
    return render_template('journal.html', user=user, current_week=current_week, entries=entries)


@app.route('/api/journal', methods=['POST'])
def save_journal_entry():
    if 'username' not in session:
        return jsonify({'error': 'לא מחוברת'}), 401
    data = request.json or {}
    week = data.get('week')
    text = data.get('text', '').strip()
    entry_id = data.get('id')
    if not text or not week:
        return jsonify({'error': 'חסר מידע'}), 400

    users = load_users()
    username = session['username']
    entries = users[username].setdefault('journal', [])

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
    save_users(users)
    return jsonify({'success': True})


@app.route('/api/journal/<entry_id>', methods=['DELETE'])
def delete_journal_entry(entry_id):
    if 'username' not in session:
        return jsonify({'error': 'לא מחוברת'}), 401
    users = load_users()
    username = session['username']
    users[username]['journal'] = [
        e for e in users[username].get('journal', []) if e['id'] != entry_id
    ]
    save_users(users)
    return jsonify({'success': True})


# ─── Appointments ────────────────────────────────────────────────────────────

@app.route('/appointments')
def appointments():
    if 'username' not in session:
        return redirect(url_for('login'))
    user, current_week, due_date, _ = get_user_context()
    if not user:
        return redirect(url_for('login'))
    appts = sorted(user.get('appointments', []), key=lambda a: a['date'])
    today = date.today().isoformat()
    upcoming = [a for a in appts if a['date'] >= today]
    past = [a for a in appts if a['date'] < today]
    return render_template('appointments.html',
        user=user, current_week=current_week,
        upcoming=upcoming, past=past, today=today)


@app.route('/api/appointments', methods=['POST'])
def save_appointment():
    if 'username' not in session:
        return jsonify({'error': 'לא מחוברת'}), 401
    data = request.json or {}
    appt_date = data.get('date', '').strip()
    appt_type = data.get('type', '').strip()
    notes = data.get('notes', '').strip()
    if not appt_date or not appt_type:
        return jsonify({'error': 'חסר מידע'}), 400

    users = load_users()
    username = session['username']
    appts = users[username].setdefault('appointments', [])
    appts.append({
        'id': uuid.uuid4().hex[:10],
        'date': appt_date,
        'type': appt_type,
        'notes': notes,
        'created_at': datetime.now().strftime('%d.%m.%Y')
    })
    save_users(users)
    return jsonify({'success': True})


@app.route('/api/appointments/<appt_id>', methods=['DELETE'])
def delete_appointment(appt_id):
    if 'username' not in session:
        return jsonify({'error': 'לא מחוברת'}), 401
    users = load_users()
    username = session['username']
    users[username]['appointments'] = [
        a for a in users[username].get('appointments', []) if a['id'] != appt_id
    ]
    save_users(users)
    return jsonify({'success': True})


# ─── Baby Names ──────────────────────────────────────────────────────────────

@app.route('/names')
def names():
    if 'username' not in session:
        return redirect(url_for('login'))
    user, current_week, due_date, _ = get_user_context()
    if not user:
        return redirect(url_for('login'))
    return render_template('names.html', user=user, current_week=current_week,
                           names=user.get('baby_names', []))


@app.route('/api/names', methods=['POST'])
def add_name():
    if 'username' not in session:
        return jsonify({'error': 'לא מחוברת'}), 401
    data = request.json or {}
    name = data.get('name', '').strip()
    gender = data.get('gender', 'unknown')
    if not name:
        return jsonify({'error': 'חסר שם'}), 400

    users = load_users()
    username = session['username']
    baby_names = users[username].setdefault('baby_names', [])
    if any(n['name'] == name for n in baby_names):
        return jsonify({'error': 'השם כבר קיים ברשימה'}), 400
    baby_names.append({'id': uuid.uuid4().hex[:10], 'name': name, 'gender': gender, 'liked': False})
    save_users(users)
    return jsonify({'success': True})


@app.route('/api/names/<name_id>/like', methods=['POST'])
def toggle_name_like(name_id):
    if 'username' not in session:
        return jsonify({'error': 'לא מחוברת'}), 401
    users = load_users()
    username = session['username']
    for n in users[username].get('baby_names', []):
        if n['id'] == name_id:
            n['liked'] = not n['liked']
            break
    save_users(users)
    return jsonify({'success': True})


@app.route('/api/names/<name_id>', methods=['DELETE'])
def delete_name(name_id):
    if 'username' not in session:
        return jsonify({'error': 'לא מחוברת'}), 401
    users = load_users()
    username = session['username']
    users[username]['baby_names'] = [
        n for n in users[username].get('baby_names', []) if n['id'] != name_id
    ]
    save_users(users)
    return jsonify({'success': True})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=True)
