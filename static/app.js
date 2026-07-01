// ─── Chat Widget ───────────────────────────────────────────────────────────

const CHAT_STORAGE_KEY = 'pt_chat_history';
const CHAT_MAX_STORED = 40; // max messages to persist

let chatHistory = [];

function _saveChatToStorage() {
    const toSave = chatHistory.slice(-CHAT_MAX_STORED);
    try { localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(toSave)); } catch {}
}

function _loadChatFromStorage() {
    try {
        const saved = localStorage.getItem(CHAT_STORAGE_KEY);
        return saved ? JSON.parse(saved) : [];
    } catch { return []; }
}

function initChat() {
    const msgs = document.getElementById('chatMessages');
    if (!msgs) return;

    const saved = _loadChatFromStorage();
    if (saved.length > 0) {
        chatHistory = saved;
        // Restore DOM messages
        saved.forEach(m => {
            const role = m.role === 'user' ? 'user' : 'agent';
            const div = document.createElement('div');
            div.className = 'message ' + role;
            div.innerHTML = m.content.replace(/\n/g, '<br>');
            msgs.appendChild(div);
        });
    } else {
        // Default greeting from Pua
        const greetDiv = document.createElement('div');
        greetDiv.className = 'message agent pua-greeting';
        greetDiv.innerHTML = `<div class="pua-msg-avatar"><img src="/static/pua-avatar.svg" alt="רחלי"></div>
            <div class="pua-msg-text">היי! אני רחלי 🌸<br>מלווה הריון ואני כאן בשבילך!<br>שאלי אותי כל מה שעל הלב 💕</div>`;
        msgs.appendChild(greetDiv);
    }
    scrollChatToBottom();
}

function toggleChat() {
    const panel = document.getElementById('chatPanel');
    const fab = document.getElementById('chatFab');
    if (!panel) return;
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) {
        fab.classList.add('open');
        document.getElementById('chatInput').focus();
        scrollChatToBottom();
    } else {
        fab.classList.remove('open');
    }
}

function clearChat() {
    if (!confirm('לנקות את השיחה עם רחלי?')) return;
    chatHistory = [];
    try { localStorage.removeItem(CHAT_STORAGE_KEY); } catch {}
    const msgs = document.getElementById('chatMessages');
    if (msgs) {
        msgs.innerHTML = '';
        const greetDiv = document.createElement('div');
        greetDiv.className = 'message agent pua-greeting';
        greetDiv.innerHTML = `<div class="pua-msg-avatar"><img src="/static/pua-avatar.svg" alt="רחלי"></div>
            <div class="pua-msg-text">היי! אני רחלי 🌸<br>מלווה הריון ואני כאן בשבילך!<br>שאלי אותי כל מה שעל הלב 💕</div>`;
        msgs.appendChild(greetDiv);
    }
    scrollChatToBottom();
}

function scrollChatToBottom() {
    const msgs = document.getElementById('chatMessages');
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

function appendMessage(role, text) {
    const msgs = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = 'message ' + role;
    if (role === 'agent') {
        div.innerHTML = `<div class="pua-msg-avatar"><img src="/static/pua-avatar.svg" alt="רחלי"></div><div class="pua-msg-text">${text.replace(/\n/g, '<br>')}</div>`;
    } else {
        div.innerHTML = text.replace(/\n/g, '<br>');
    }
    msgs.appendChild(div);
    scrollChatToBottom();
    return div;
}

async function sendMessage() {
    const input = document.getElementById('chatInput');
    const btn = document.getElementById('sendBtn');
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    input.disabled = true;
    btn.disabled = true;

    appendMessage('user', text);
    chatHistory.push({ role: 'user', content: text });

    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message loading pua-loading';
    loadingDiv.innerHTML = `<div class="pua-msg-avatar"><img src="/static/pua-avatar.svg" alt="רחלי"></div><div class="pua-typing"><span></span><span></span><span></span></div>`;
    document.getElementById('chatMessages').appendChild(loadingDiv);
    scrollChatToBottom();

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: chatHistory })
        });
        const data = await res.json();
        loadingDiv.remove();

        if (data.reply) {
            chatHistory.push({ role: 'assistant', content: data.reply });
            _saveChatToStorage();
            appendMessage('agent', data.reply);
        } else {
            appendMessage('agent', 'מצטערת, משהו השתבש. נסי שוב 🙏');
        }
    } catch {
        loadingDiv.remove();
        appendMessage('agent', 'בעיית תקשורת. נסי שוב בעוד רגע 💕');
    }

    input.disabled = false;
    btn.disabled = false;
    input.focus();
}

// ─── Gallery (IndexedDB — photos stored locally on device) ─────────────────

const _DB_NAME = 'beten-gedola-photos';
const _DB_VER = 1;
const _STORE = 'photos';
let _db = null;

function _openDB() {
    return new Promise((resolve, reject) => {
        if (_db) { resolve(_db); return; }
        const req = indexedDB.open(_DB_NAME, _DB_VER);
        req.onupgradeneeded = e => {
            const d = e.target.result;
            if (!d.objectStoreNames.contains(_STORE)) {
                d.createObjectStore(_STORE, { keyPath: 'id', autoIncrement: true });
            }
        };
        req.onsuccess = e => { _db = e.target.result; resolve(_db); };
        req.onerror = e => reject(e.target.error);
    });
}

async function _getAllPhotos() {
    const d = await _openDB();
    return new Promise((resolve, reject) => {
        const req = d.transaction(_STORE, 'readonly').objectStore(_STORE).getAll();
        req.onsuccess = () => resolve(req.result);
        req.onerror = e => reject(e.target.error);
    });
}

async function _getPhotosByCategory(category) {
    const all = await _getAllPhotos();
    return all.filter(p => (p.category || 'belly') === category);
}

async function _getPhoto(id) {
    const d = await _openDB();
    return new Promise((resolve, reject) => {
        const req = d.transaction(_STORE, 'readonly').objectStore(_STORE).get(id);
        req.onsuccess = () => resolve(req.result);
        req.onerror = e => reject(e.target.error);
    });
}

async function _addPhoto(blob, week, caption, category) {
    const d = await _openDB();
    return new Promise((resolve, reject) => {
        const req = d.transaction(_STORE, 'readwrite').objectStore(_STORE).add({
            blob,
            week: parseInt(week),
            caption,
            category: category || 'belly',
            uploadedAt: new Date().toLocaleDateString('he-IL')
        });
        req.onsuccess = () => resolve(req.result);
        req.onerror = e => reject(e.target.error);
    });
}

async function _deletePhoto(id) {
    const d = await _openDB();
    return new Promise((resolve, reject) => {
        const req = d.transaction(_STORE, 'readwrite').objectStore(_STORE).delete(id);
        req.onsuccess = () => resolve();
        req.onerror = e => reject(e.target.error);
    });
}

async function loadGallery() {
    const grid = document.getElementById('galleryGrid');
    const empty = document.getElementById('emptyGallery');
    const countEl = document.getElementById('photoCount');
    if (!grid) return;

    const photos = (await _getPhotosByCategory('belly')).sort((a, b) => a.week - b.week);
    if (countEl) countEl.textContent = photos.length;

    if (photos.length === 0) {
        grid.style.display = 'none';
        if (empty) empty.style.display = '';
        return;
    }

    if (empty) empty.style.display = 'none';
    grid.style.display = '';
    grid.innerHTML = '';

    for (const photo of photos) {
        const url = URL.createObjectURL(photo.blob);
        const card = document.createElement('div');
        card.className = 'photo-card';
        card.id = 'photo-' + photo.id;
        card.innerHTML = `
            <img src="${url}" alt="שבוע ${photo.week}" loading="lazy">
            <div class="photo-week-badge">שבוע ${photo.week}</div>
            ${photo.caption ? `<div class="photo-overlay">${photo.caption.replace(/</g,'&lt;')}</div>` : ''}
            <button class="photo-delete" onclick="deletePhotoLocal(${photo.id})" title="מחיקה">🗑️</button>
        `;
        grid.appendChild(card);
    }
}

async function deletePhotoLocal(id) {
    if (!confirm('למחוק את התמונה?')) return;
    const card = document.getElementById('photo-' + id);
    if (card) card.style.opacity = '0.4';
    try {
        await _deletePhoto(id);
        if (card) card.remove();
        const photos = await _getAllPhotos();
        const countEl = document.getElementById('photoCount');
        if (countEl) countEl.textContent = photos.length;
        if (photos.length === 0) {
            const grid = document.getElementById('galleryGrid');
            const empty = document.getElementById('emptyGallery');
            if (grid) grid.style.display = 'none';
            if (empty) empty.style.display = '';
        }
    } catch {
        if (card) card.style.opacity = '1';
        alert('שגיאה במחיקה');
    }
}

function openUploadModal() {
    const modal = document.getElementById('uploadModal');
    if (modal) modal.classList.add('open');
}

function closeUploadModal() {
    const modal = document.getElementById('uploadModal');
    if (!modal) return;
    modal.classList.remove('open');
    document.getElementById('uploadCaption').value = '';
    document.getElementById('photoPreview').innerHTML = '';
    const area = document.getElementById('uploadArea');
    area.innerHTML = `
        <input type="file" id="photoFile" accept="image/*" onchange="handleFileSelect(this)">
        <div class="upload-icon">📷</div>
        <div class="upload-text">לחצי לבחירת תמונה<br>או גררי לכאן</div>
    `;
    bindUploadAreaClick();
}

function bindUploadAreaClick() {
    const area = document.getElementById('uploadArea');
    if (!area) return;
    area.addEventListener('click', () => document.getElementById('photoFile')?.click());
    area.addEventListener('dragover', e => { e.preventDefault(); area.classList.add('dragover'); });
    area.addEventListener('dragleave', () => area.classList.remove('dragover'));
    area.addEventListener('drop', e => {
        e.preventDefault();
        area.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) {
            const dt = new DataTransfer();
            dt.items.add(file);
            document.getElementById('photoFile').files = dt.files;
            handleFileSelect(document.getElementById('photoFile'));
        }
    });
}

function handleFileSelect(input) {
    const file = input.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = e => {
        document.getElementById('photoPreview').innerHTML =
            `<img src="${e.target.result}" alt="תצוגה מקדימה">`;
    };
    reader.readAsDataURL(file);
}

async function submitUpload() {
    const fileInput = document.getElementById('photoFile');
    const week = document.getElementById('uploadWeek').value;
    const caption = document.getElementById('uploadCaption').value.trim();
    const btn = document.getElementById('uploadBtn');

    if (!fileInput || !fileInput.files[0]) {
        alert('יש לבחור תמונה');
        return;
    }

    btn.disabled = true;
    btn.textContent = 'שומרת...';

    try {
        await _addPhoto(fileInput.files[0], week, caption);
        closeUploadModal();
        await loadGallery();
    } catch (e) {
        alert('שגיאה בשמירה: ' + e.message);
        btn.disabled = false;
        btn.textContent = 'שמירה';
    }
}

// ─── Journal ───────────────────────────────────────────────────────────────

function openJournalModal(id, week, text) {
    document.getElementById('editEntryId').value = id || '';
    if (week) document.getElementById('journalWeek').value = week;
    document.getElementById('journalText').value = text || '';
    document.querySelector('#journalModal .modal-title').textContent = id ? '✏️ עריכת רשומה' : '📓 רשומה חדשה';
    document.getElementById('journalModal').classList.add('open');
    setTimeout(() => document.getElementById('journalText').focus(), 100);
}

function closeJournalModal() {
    document.getElementById('journalModal').classList.remove('open');
    document.getElementById('journalText').value = '';
    document.getElementById('editEntryId').value = '';
}

function editEntry(id, week, text) {
    openJournalModal(id, week, text);
}

async function submitJournal() {
    const text = document.getElementById('journalText').value.trim();
    const week = document.getElementById('journalWeek').value;
    const id = document.getElementById('editEntryId').value;
    if (!text) { alert('יש לכתוב משהו'); return; }

    const res = await fetch('/api/journal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ week: parseInt(week), text, id: id || undefined })
    });
    if ((await res.json()).success) location.reload();
}

async function deleteEntry(id) {
    if (!confirm('למחוק את הרשומה?')) return;
    const card = document.getElementById('jentry-' + id);
    if (card) card.style.opacity = '0.4';
    const res = await fetch('/api/journal/' + id, { method: 'DELETE' });
    if ((await res.json()).success) { if (card) card.remove(); }
    else { if (card) card.style.opacity = '1'; alert('שגיאה'); }
}

// ─── Appointments ──────────────────────────────────────────────────────────

function openApptModal() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('apptDate').value = today;
    document.getElementById('apptNotes').value = '';
    document.getElementById('apptModal').classList.add('open');
}

function closeApptModal() {
    document.getElementById('apptModal').classList.remove('open');
}

async function submitAppt() {
    const type = document.getElementById('apptType').value;
    const date = document.getElementById('apptDate').value;
    const notes = document.getElementById('apptNotes').value.trim();
    if (!date) { alert('יש לבחור תאריך'); return; }

    const res = await fetch('/api/appointments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, date, notes })
    });
    if ((await res.json()).success) location.reload();
}

async function deleteAppt(id) {
    if (!confirm('למחוק את התור?')) return;
    const card = document.getElementById('appt-' + id);
    if (card) card.style.opacity = '0.4';
    const res = await fetch('/api/appointments/' + id, { method: 'DELETE' });
    if ((await res.json()).success) { if (card) card.remove(); }
    else { if (card) card.style.opacity = '1'; alert('שגיאה'); }
}

// ─── Baby Names ────────────────────────────────────────────────────────────

function openNameModal() {
    document.getElementById('nameInput').value = '';
    document.querySelector('input[name="gender"][value="unknown"]').checked = true;
    document.getElementById('nameModal').classList.add('open');
    setTimeout(() => document.getElementById('nameInput').focus(), 100);
}

function closeNameModal() {
    document.getElementById('nameModal').classList.remove('open');
}

async function submitName() {
    const name = document.getElementById('nameInput').value.trim();
    const gender = document.querySelector('input[name="gender"]:checked')?.value || 'unknown';
    if (!name) { alert('יש להכניס שם'); return; }

    const res = await fetch('/api/names', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, gender })
    });
    const data = await res.json();
    if (data.success) location.reload();
    else alert(data.error || 'שגיאה');
}

async function toggleLike(id, btn) {
    const card = document.getElementById('name-' + id);
    const res = await fetch('/api/names/' + id + '/like', { method: 'POST' });
    if ((await res.json()).success) {
        const isLiked = btn.classList.contains('liked');
        btn.classList.toggle('liked');
        btn.textContent = isLiked ? '🤍' : '❤️';
        card.dataset.liked = isLiked ? 'false' : 'true';
        const activeTab = document.querySelector('.name-tab.active');
        if (activeTab) filterNames(activeTab.dataset.filter || 'all', activeTab);
    }
}

async function deleteName(id) {
    if (!confirm('להסיר את השם?')) return;
    const card = document.getElementById('name-' + id);
    if (card) card.style.opacity = '0.4';
    const res = await fetch('/api/names/' + id, { method: 'DELETE' });
    if ((await res.json()).success) { if (card) card.remove(); }
    else { if (card) card.style.opacity = '1'; alert('שגיאה'); }
}

function filterNames(filter, tabEl) {
    document.querySelectorAll('.name-tab').forEach(t => t.classList.remove('active'));
    tabEl.classList.add('active');
    tabEl.dataset.filter = filter;
    document.querySelectorAll('.name-card').forEach(card => {
        const gender = card.dataset.gender;
        const liked = card.dataset.liked === 'true';
        let show = true;
        if (filter === 'liked') show = liked;
        else if (filter === 'boy') show = gender === 'boy';
        else if (filter === 'girl') show = gender === 'girl';
        else if (filter === 'unknown') show = gender === 'unknown';
        card.style.display = show ? '' : 'none';
    });
}

// ─── Fruit Image (Wikipedia) ───────────────────────────────────────────────

const FRUIT_WIKI_TITLES = {
    1:'Poppy_seed', 2:'Sesame', 3:'Strawberry', 4:'Poppy_seed',
    5:'Sesame', 6:'Lentil', 7:'Blueberry', 8:'Raspberry',
    9:'Grape', 10:'Plum', 11:'Fig', 12:'Lime_(fruit)',
    13:'Cherry_tomato', 14:'Lemon', 15:'Apple', 16:'Avocado',
    17:'Pear', 18:'Bell_pepper', 19:'Mango', 20:'Banana',
    21:'Carrot', 22:'Cucumber', 23:'Grapefruit', 24:'Maize',
    25:'Daikon', 26:'Cauliflower', 27:'Cauliflower', 28:'Eggplant',
    29:'Pumpkin', 30:'Cabbage', 31:'Coconut', 32:'Pumpkin',
    33:'Pineapple', 34:'Zucchini', 35:'Watermelon', 36:'Papaya',
    37:'Cabbage', 38:'Leek', 39:'Watermelon', 40:'Watermelon'
};

async function loadFruitImage(weekNum) {
    const title = FRUIT_WIKI_TITLES[weekNum];
    if (!title) return;
    const cacheKey = 'fwiki_' + weekNum;
    let src = sessionStorage.getItem(cacheKey);
    if (!src) {
        try {
            const r = await fetch('https://en.wikipedia.org/api/rest_v1/page/summary/' + encodeURIComponent(title));
            const d = await r.json();
            src = d.thumbnail?.source?.replace('/320px-', '/400px-') || '';
            if (src) sessionStorage.setItem(cacheKey, src);
        } catch { return; }
    }
    if (!src) return;
    const img = document.getElementById('fruitImg');
    if (!img) return;
    img.onload = () => {
        img.style.display = 'block';
        const em = document.getElementById('fruitEmoji');
        if (em) em.style.display = 'none';
    };
    img.onerror = () => {};
    img.src = src;
}

// ─── Belly Chart ───────────────────────────────────────────────────────────

function renderBellyChart(measurements) {
    const svg = document.getElementById('bellySvg');
    if (!svg) return;
    if (!measurements || measurements.length === 0) {
        svg.innerHTML = '<text x="50%" y="100" text-anchor="middle" fill="#8A6A8A" font-size="14" font-family="Heebo">אין נתונים עדיין — הוסיפי מדידה ראשונה 💕</text>';
        svg.setAttribute('height', '140');
        return;
    }

    const W = svg.parentElement.clientWidth || 600;
    const H = 220;
    svg.setAttribute('height', H);
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);

    const pad = { top: 24, right: 24, bottom: 44, left: 52 };
    const cW = W - pad.left - pad.right;
    const cH = H - pad.top - pad.bottom;

    const weeks = measurements.map(m => m.week);
    const cms = measurements.map(m => m.cm);
    const minW = Math.min(...weeks); const maxW = Math.max(...weeks, minW + 1);
    const minC = Math.min(...cms) - 4;  const maxC = Math.max(...cms) + 4;

    const xS = w => pad.left + (w - minW) / (maxW - minW || 1) * cW;
    const yS = c => pad.top + cH - (c - minC) / (maxC - minC || 1) * cH;

    let out = `<defs><linearGradient id="bellyGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#D4739A" stop-opacity="0.18"/>
        <stop offset="100%" stop-color="#D4739A" stop-opacity="0"/>
    </linearGradient></defs>`;

    // grid
    const gridStep = cH > 120 ? 5 : 10;
    for (let c = Math.ceil(minC / gridStep) * gridStep; c <= maxC; c += gridStep) {
        const y = yS(c);
        out += `<line x1="${pad.left}" y1="${y}" x2="${pad.left + cW}" y2="${y}" stroke="#F0D8E8" stroke-width="1"/>`;
        out += `<text x="${pad.left - 6}" y="${y + 4}" text-anchor="end" font-size="11" fill="#8A6A8A" font-family="Heebo">${c}</text>`;
    }
    // x axis
    out += `<line x1="${pad.left}" y1="${pad.top + cH}" x2="${pad.left + cW}" y2="${pad.top + cH}" stroke="#F0D8E8" stroke-width="1"/>`;

    const pts = measurements.map(m => `${xS(m.week)},${yS(m.cm)}`).join(' ');
    const m0 = measurements[0]; const mN = measurements[measurements.length - 1];
    out += `<polygon points="${xS(m0.week)},${pad.top + cH} ${pts} ${xS(mN.week)},${pad.top + cH}" fill="url(#bellyGrad)"/>`;
    out += `<polyline points="${pts}" fill="none" stroke="#D4739A" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>`;

    measurements.forEach(m => {
        const x = xS(m.week); const y = yS(m.cm);
        out += `<circle cx="${x}" cy="${y}" r="5" fill="#D4739A" stroke="white" stroke-width="2.5"/>`;
        out += `<text x="${x}" y="${y - 10}" text-anchor="middle" font-size="11" fill="#D4739A" font-weight="700" font-family="Heebo">${m.cm}</text>`;
        out += `<text x="${x}" y="${H - 8}" text-anchor="middle" font-size="11" fill="#8A6A8A" font-family="Heebo">ש${m.week}</text>`;
    });

    out += `<text x="14" y="${pad.top + cH / 2}" text-anchor="middle" transform="rotate(-90,14,${pad.top + cH / 2})" font-size="11" fill="#8A6A8A" font-family="Heebo">ס"מ</text>`;
    svg.innerHTML = out;
}

// ─── Dark Mode ───────────────────────────────────────────────────────────────

function toggleTheme() {
    const isDark = document.documentElement.classList.toggle('dark-mode');
    try { localStorage.setItem('pt_theme', isDark ? 'dark' : 'light'); } catch {}
    _updateThemeBtn();
}

function _updateThemeBtn() {
    const btn = document.getElementById('themeToggleBtn');
    if (!btn) return;
    const isDark = document.documentElement.classList.contains('dark-mode');
    btn.textContent = isDark ? '☀️ מצב בהיר' : '🌙 מצב כהה';
}

// ─── PWA Install ───────────────────────────────────────────────────────────

let deferredInstallPrompt = null;

function _isStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
}

function _isIOS() {
    return /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
}

function _initInstallButton() {
    const btn = document.getElementById('installAppBtn');
    if (!btn || _isStandalone()) return;

    if (_isIOS()) {
        btn.style.display = 'block';
        return;
    }

    window.addEventListener('beforeinstallprompt', e => {
        e.preventDefault();
        deferredInstallPrompt = e;
        btn.style.display = 'block';
    });

    window.addEventListener('appinstalled', () => {
        deferredInstallPrompt = null;
        btn.style.display = 'none';
    });
}

async function installApp() {
    if (_isIOS()) {
        const modal = document.getElementById('installInstructionsModal');
        if (modal) modal.classList.add('open');
        return;
    }
    if (!deferredInstallPrompt) return;
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    const btn = document.getElementById('installAppBtn');
    if (btn) btn.style.display = 'none';
}

function closeInstallInstructionsModal() {
    const modal = document.getElementById('installInstructionsModal');
    if (modal) modal.classList.remove('open');
}

// ─── Init ──────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
    initChat();
    bindUploadAreaClick();
    _updateThemeBtn();
    _initInstallButton();

    const modalHandlers = [
        ['uploadModal', closeUploadModal],
        ['journalModal', closeJournalModal],
        ['apptModal', closeApptModal],
        ['nameModal', closeNameModal],
        ['installInstructionsModal', closeInstallInstructionsModal],
    ];
    modalHandlers.forEach(([id, fn]) => {
        const m = document.getElementById(id);
        if (m) m.addEventListener('click', e => { if (e.target === m) fn(); });
    });
});
