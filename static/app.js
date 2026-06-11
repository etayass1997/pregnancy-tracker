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

// ─── Init ──────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
    bindUploadAreaClick();

    // Close modal on backdrop click
    const modal = document.getElementById('uploadModal');
    if (modal) {
        modal.addEventListener('click', e => {
            if (e.target === modal) closeUploadModal();
        });
    }
});
