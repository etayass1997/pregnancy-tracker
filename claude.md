# בטן גדולה — סוכן מעקב הריון

## תיאור
אפליקציית Flask למעקב הריון שבועי (40 שבועות). כוללת דשבורד שבועי עם גודל העובר (פרי השבוע מ-Wikipedia), צ'אט עם רחלי (AI), גלריית תמונות, יומן, תורים, שמות, בעיטות, מצב רוח, צ'קליסט לידה, מדידות בטן, משקל, לחץ דם, תסמינים, שאלות לרופא, תוכנית לידה, טיימר צירים, תזונה, הישגים, תרגילים, ויטמינים, מד שתייה, מעקב שינה, מעקב סוכר, תוצאות בדיקות, קיגל, שינויי עור, רשימת ציוד, תיק לבית חולים, אנשי קשר לחירום, השוואת תמונות בטן, וייצוא יומן. מזהה משתמש לפי cookie (device ID) — אין login.

## הערות טכניות חשובות
- תמונות (גלריה + שינויי עור) נשמרות ב-**IndexedDB בדפדפן** (לא בשרת) — ראו `_addPhoto`/`_getPhotosByCategory` ב-`app.js`. שדה `category` מבחין בין 'belly' (גלריה) ל-'skin'.
- ⚠️ ב-Jinja, שדה בשם `items` בתוך dict נגיש רק עם `entry['items']` ולא `entry.items` (מתנגש עם המתודה המובנית של dict).
- מצב כהה: מחלקת `dark-mode` על `<html>`, נשמר ב-`localStorage['pt_theme']`, טוגל דרך `toggleTheme()`.
- ייצוא PDF (יומן) מבוסס על תבנית הדפסה נפרדת (`journal_export.html`) + `window.print()` — לא ספריית PDF, כדי להימנע מבעיות RTL עברית.

## סטאק
- **Backend**: Flask (Python), port 5002
- **AI**: Anthropic Claude (Lotus — אישיות חמה ותומכת)
- **שמירה**: קבצי JSON לפי device_id (תיקיית `data/`)
- **תמונות**: `uploads/` — גלריית בטן
- **Frontend**: `templates/` (Jinja HTML)
- **דפלוי**: Render

## קבצים מרכזיים
| קובץ | תפקיד |
|------|--------|
| `app.py` | Flask backend + Lotus AI |
| `pregnancy_data.py` | נתוני 40 שבועות + `WEEK_FRUIT_WIKI` |
| `templates/` | כל דפי ה-UI |
| `data/` | נתוני משתמשים (JSON per device) |
| `uploads/` | תמונות בטן שהועלו |

## הרצה מקומית
```bash
pip install -r requirements.txt
# צור .env עם ANTHROPIC_API_KEY=sk-ant-...
python app.py   # http://localhost:5002
```
