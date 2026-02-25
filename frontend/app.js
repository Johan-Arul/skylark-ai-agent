/**
 * app.js — Skylark BI Agent Chat Interface
 * Handles conversation state, API calls, markdown rendering, and UI updates.
 */

const API_BASE = window.location.origin;

let conversationHistory = [];
let isLoading = false;

// ─── Markdown renderer (lightweight, no dependencies) ───────────────────────

function renderMarkdown(text) {
    if (!text) return '';
    let html = text
        // Escape HTML first
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        // Headers
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        // Bold and italic
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        // Code
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        // Bullet lists (handle - and *)
        .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
        // Numbered lists
        .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
        // Wrap consecutive <li> in <ul>
        .replace(/(<li>.*<\/li>)/s, (match) => `<ul>${match}</ul>`)
        // Blockquotes (for caveats)
        .replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
        // Horizontal rule
        .replace(/^---$/gm, '<hr />')
        // Line breaks → paragraphs
        .split('\n\n')
        .map(p => p.trim())
        .filter(p => p)
        .map(p => {
            if (p.startsWith('<h') || p.startsWith('<ul') || p.startsWith('<li') ||
                p.startsWith('<hr') || p.startsWith('<blockquote')) return p;
            return `<p>${p.replace(/\n/g, '<br />')}</p>`;
        })
        .join('\n');

    return html;
}


// ─── Intent badge ────────────────────────────────────────────────────────────

function getIntentBadge(intent) {
    const labels = {
        revenue: '💰 Revenue',
        pipeline: '📋 Pipeline',
        operations: '🔧 Operations',
        crossboard: '🔄 Cross-Board',
        leadership: '📊 Leadership',
        ambiguous: '❓ Clarifying',
    };
    const cls = intent || 'ambiguous';
    return `<span class="intent-badge intent-${cls}">${labels[cls] || cls}</span>`;
}


// ─── Message rendering ───────────────────────────────────────────────────────

function appendMessage(role, content, meta = {}) {
    const container = document.getElementById('messages');

    // Remove welcome screen on first message
    const welcome = container.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    const div = document.createElement('div');
    div.className = `message ${role}`;

    const avatar = role === 'user' ? '👤' : '🤖';
    const timestamp = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });

    let caveatHtml = '';
    if (meta.caveats && meta.caveats.trim()) {
        caveatHtml = `<div class="msg-caveat">${meta.caveats.replace(/\n/g, '<br>')}</div>`;
    }

    let metaHtml = '';
    if (role === 'assistant' && meta.intent) {
        metaHtml = `<div class="msg-meta">${getIntentBadge(meta.intent)} ${timestamp}</div>`;
    } else {
        metaHtml = `<div class="msg-meta">${timestamp}</div>`;
    }

    div.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div class="msg-content">
      <div class="msg-bubble">${role === 'assistant' ? renderMarkdown(content) : escapeHtml(content)}</div>
      ${caveatHtml}
      ${metaHtml}
    </div>
  `;

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>');
}


// ─── API calls ───────────────────────────────────────────────────────────────

async function sendMessage() {
    const input = document.getElementById('user-input');
    const message = input.value.trim();
    if (!message || isLoading) return;

    // Clear input
    input.value = '';
    input.style.height = 'auto';
    setLoading(true);

    // Add to UI
    appendMessage('user', message);
    conversationHistory.push({ role: 'user', content: message });

    try {
        const res = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                conversation_history: conversationHistory.slice(-10),
            }),
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Server error (${res.status})`);
        }

        const data = await res.json();
        appendMessage('assistant', data.response, {
            intent: data.intent,
            caveats: data.caveats,
        });
        conversationHistory.push({ role: 'assistant', content: data.response });

    } catch (err) {
        appendMessage('assistant', `⚠️ **Error:** ${err.message}`, { intent: 'ambiguous' });
        showToast(err.message);
    } finally {
        setLoading(false);
        input.focus();
    }
}

async function requestLeadership() {
    if (isLoading) return;
    setLoading(true);

    appendMessage('user', '📊 Generate Leadership Update');
    conversationHistory.push({ role: 'user', content: 'Give me the full leadership update for this quarter.' });

    try {
        const res = await fetch(`${API_BASE}/leadership-update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Server error (${res.status})`);
        }

        const data = await res.json();
        appendMessage('assistant', data.response, {
            intent: 'leadership',
            caveats: data.caveats,
        });
        conversationHistory.push({ role: 'assistant', content: data.response });

    } catch (err) {
        appendMessage('assistant', `⚠️ **Error:** ${err.message}`, { intent: 'leadership' });
        showToast(err.message);
    } finally {
        setLoading(false);
    }
}

async function refreshData() {
    const btn = document.getElementById('refresh-btn');
    btn.classList.add('spinning');
    btn.disabled = true;

    try {
        const res = await fetch(`${API_BASE}/refresh`, { method: 'POST' });
        const data = await res.json();

        if (res.ok) {
            showToast('✅ ' + data.message, 'success');
            await checkStatus();
        } else {
            showToast('⚠️ ' + (data.detail || 'Refresh failed'));
        }
    } catch (err) {
        showToast('Connection error: ' + err.message);
    } finally {
        btn.classList.remove('spinning');
        btn.disabled = false;
    }
}

function sendQuick(text) {
    if (isLoading) return;
    const input = document.getElementById('user-input');
    input.value = text;
    sendMessage();
}

async function checkStatus() {
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');

    dot.className = 'status-dot loading';
    text.textContent = 'Connecting...';

    try {
        const res = await fetch(`${API_BASE}/health`);
        const data = await res.json();

        if (data.status === 'ok' && data.data_loaded) {
            dot.className = 'status-dot ok';
            const deals = data.deals_count || 0;
            const wos = data.workorders_count || 0;
            text.textContent = `Live · ${deals} deals · ${wos} WOs`;
        } else if (data.status === 'ok') {
            dot.className = 'status-dot loading';
            text.textContent = 'Connected · No data yet';
        } else {
            dot.className = 'status-dot error';
            text.textContent = data.message || 'Config needed';
        }
    } catch {
        dot.className = 'status-dot error';
        text.textContent = 'Server offline';
    }
}


// ─── UI helpers ──────────────────────────────────────────────────────────────

function setLoading(state) {
    isLoading = state;
    const typing = document.getElementById('typing');
    const sendBtn = document.getElementById('send-btn');
    const input = document.getElementById('user-input');

    if (state) {
        typing.classList.remove('hidden');
        sendBtn.disabled = true;
        input.disabled = true;
        document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
    } else {
        typing.classList.add('hidden');
        sendBtn.disabled = false;
        input.disabled = false;
    }
}

function clearChat() {
    conversationHistory = [];
    const messages = document.getElementById('messages');
    messages.innerHTML = `
    <div class="welcome-message">
      <div class="welcome-icon">🚁</div>
      <h2>Welcome to Skylark BI</h2>
      <p>I'm your AI business intelligence analyst. Ask me founder-level questions like:</p>
      <div class="example-queries">
        <div class="example-chip" onclick="sendQuick('How is our pipeline looking this quarter?')">How is our pipeline looking this quarter?</div>
        <div class="example-chip" onclick="sendQuick('What revenue can we expect this month?')">What revenue can we expect this month?</div>
        <div class="example-chip" onclick="sendQuick('Are we operationally overloaded?')">Are we operationally overloaded?</div>
        <div class="example-chip" onclick="sendQuick('What is our deal-to-project conversion rate?')">What is our deal-to-project conversion rate?</div>
      </div>
    </div>
  `;
}

function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
}

function showToast(message, type = 'error') {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.style.borderColor = type === 'success' ? 'rgba(86, 216, 137, 0.4)' : '';
    toast.style.color = type === 'success' ? 'var(--green)' : '';
    toast.style.background = type === 'success' ? 'rgba(86, 216, 137, 0.1)' : '';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4500);
}


// ─── Init ────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    checkStatus();
    // Refresh status every 60 seconds
    setInterval(checkStatus, 60000);
    // Focus input
    document.getElementById('user-input').focus();
});
