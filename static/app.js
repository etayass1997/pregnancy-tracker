// ─── Chat Widget ───────────────────────────────────────────────────────────

const chatHistory = [];

function toggleChat() {
    const panel = document.getElementById('chatPanel');
    const fab = document.getElementById('chatFab');
    if (!panel) return;
    panel.classList.toggle('open');
    fab.style.transform = panel.classList.contains('open') ? 'scale(0.9)' : '';
    if (panel.classList.contains('open')) {
        document.getElementById('chatInput').focus();
        scrollChatToBottom();
    }
}

function scrollChatToBottom() {
    const msgs = document.getElementById('chatMessages');
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

function appendMessage(role, text) {
    const msgs = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = 'message ' + role;
    div.innerHTML = text.replace(/\n/g, '<br>');
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

    const loading = appendMessage('loading', 'הריונית מקלידה...');

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: chatHistory })
        });
        const data = await res.json();
        loading.remove();

        if (data.reply) {
            chatHistory.push({ role: 'assistant', content: data.reply });
            appendMessage('agent', data.reply);
        } else {
            appendMessage('agent', 'מצטערת, משהו השתבש. נסי שוב.');
        }
    } catch {
        loading.remove();
        appendMessage('agent', 'בעיית תקשורת. נסי שוב בעוד רגע.');
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

async function _addPhoto(blob, week, caption) {
    const d = await _openDB();
    return new Promise((resolve, reject) => {
        const req = d.transaction(_STORE, 'readwrite').objectStore(_STORE).add({
            blob,
            week: parseInt(week),
            caption,
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

    const photos = (await _getAllPhotos()).sort((a, b) => a.week - b.week);
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

// ─── Init ──────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
    bindUploadAreaClick();

    const modalHandlers = [
        ['uploadModal', closeUploadModal],
        ['journalModal', closeJournalModal],
        ['apptModal', closeApptModal],
        ['nameModal', closeNameModal],
    ];
    modalHandlers.forEach(([id, fn]) => {
        const m = document.getElementById(id);
        if (m) m.addEventListener('click', e => { if (e.target === m) fn(); });
    });
});
