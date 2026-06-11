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

    const loading = appendMessage('loading', 'לוטוס מקלידה...');

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

// ─── Gallery ───────────────────────────────────────────────────────────────

function openUploadModal() {
    const modal = document.getElementById('uploadModal');
    if (modal) modal.classList.add('open');
}

function closeUploadModal() {
    const modal = document.getElementById('uploadModal');
    if (!modal) return;
    modal.classList.remove('open');
    document.getElementById('uploadForm').reset();
    document.getElementById('photoPreview').innerHTML = '';
    const area = document.getElementById('uploadArea');
    area.innerHTML = `
        <input type="file" name="photo" id="photoFile" accept="image/*" onchange="handleFileSelect(this)">
        <div class="upload-icon">📷</div>
        <div class="upload-text">לחצי לבחירת תמונה<br>או גררי לכאן</div>
    `;
    bindUploadAreaClick();
}

function bindUploadAreaClick() {
    const area = document.getElementById('uploadArea');
    if (!area) return;
    area.addEventListener('click', () => document.getElementById('photoFile').click());
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
    const form = document.getElementById('uploadForm');
    const fileInput = document.getElementById('photoFile');
    const btn = document.getElementById('uploadBtn');

    if (!fileInput.files[0]) {
        alert('יש לבחור תמונה');
        return;
    }

    btn.disabled = true;
    btn.textContent = 'מעלה...';

    const fd = new FormData(form);
    try {
        const res = await fetch('/upload', { method: 'POST', body: fd });
        const data = await res.json();
        if (data.success) {
            location.reload();
        } else {
            alert(data.error || 'שגיאה בהעלאה');
            btn.disabled = false;
            btn.textContent = 'העלאה';
        }
    } catch {
        alert('שגיאת רשת, נסי שוב');
        btn.disabled = false;
        btn.textContent = 'העלאה';
    }
}

async function deletePhoto(filename, event) {
    event.stopPropagation();
    if (!confirm('למחוק את התמונה?')) return;

    const card = document.getElementById('photo-' + filename);
    if (card) card.style.opacity = '0.4';

    try {
        const res = await fetch('/delete-photo/' + encodeURIComponent(filename), { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            if (card) card.remove();
        } else {
            if (card) card.style.opacity = '1';
            alert('לא הצלחתי למחוק');
        }
    } catch {
        if (card) card.style.opacity = '1';
        alert('שגיאת רשת');
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

    // Close modals on backdrop click
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
