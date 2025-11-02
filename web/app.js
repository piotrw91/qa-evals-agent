(() => {
  const messagesEl = document.getElementById('messages');
  const typingEl = document.getElementById('typing-indicator');
  const toolCallsEl = document.getElementById('tool-calls');
  const formEl = document.getElementById('chat-form');
  const inputEl = document.getElementById('message-input');

  function getOrCreateSessionId() {
    let sid = localStorage.getItem('qaAgentSessionId');
    if (!sid) {
      sid = self.crypto?.randomUUID?.() || (Date.now().toString(36) + Math.random().toString(36).slice(2, 10));
      localStorage.setItem('qaAgentSessionId', sid);
    }
    return sid;
  }

  const sessionId = getOrCreateSessionId();
  let awaitingResponse = false;
  let toolActiveCount = 0;
  let hideToolTimer = null;

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addMessage(text, role) {
    const row = document.createElement('div');
    row.className = `message ${role}`;
    const content = document.createElement('div');
    content.className = 'content';
    if (role === 'agent' && window.marked) {
      let html = window.marked.parse(text || '');
      if (window.DOMPurify) html = window.DOMPurify.sanitize(html);
      content.innerHTML = html;
    } else {
      content.textContent = text;
    }
    row.appendChild(content);
    messagesEl.appendChild(row);
    scrollToBottom();
  }

  function showTyping() { typingEl.classList.remove('hidden'); }
  function hideTyping() { typingEl.classList.add('hidden'); }

  function showToolPopup(name, args) {
    if (hideToolTimer) {
      clearTimeout(hideToolTimer);
      hideToolTimer = null;
    }
    const pretty = JSON.stringify(args);
    toolCallsEl.classList.add('visible');
    toolCallsEl.innerHTML = `<span class="tool">Calling <strong>${name}</strong> <code>${pretty}</code></span>`;
  }

  function hideToolPopup() {
    toolCallsEl.classList.remove('visible');
    toolCallsEl.innerHTML = '';
  }

  function openSSE() {
    const es = new EventSource(`/api/events?sessionId=${encodeURIComponent(sessionId)}`);
    es.addEventListener('tool_call', (ev) => {
      try {
        const data = JSON.parse(ev.data || '{}');
        toolActiveCount += 1;
        showToolPopup(data.name, data.args);
      } catch {}
    });
    es.addEventListener('tool_end', () => {
      toolActiveCount = Math.max(0, toolActiveCount - 1);
      if (toolActiveCount === 0) {
        hideToolTimer = setTimeout(() => {
          hideToolPopup();
          hideToolTimer = null;
        }, 5000);
      }
    });
    es.addEventListener('typing_start', () => showTyping());
    es.addEventListener('typing_end', () => {
      hideTyping();
      // Do not hide tool popup here; allow the post-tool delay to apply
    });
    es.addEventListener('final', (ev) => {
      hideTyping();
      try {
        const data = JSON.parse(ev.data || '{}');
        if (awaitingResponse) {
          addMessage(data.assistantMessage || '', 'agent');
          awaitingResponse = false;
        }
      } catch {}
    });
    es.addEventListener('ping', () => {});
    es.onerror = () => {
      // Let browser auto-reconnect. No-op.
    };
  }

  openSSE();

  formEl.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = (inputEl.value || '').trim();
    if (!message) return;

    addMessage(message, 'user');
    inputEl.value = '';
    awaitingResponse = true;
    showTyping();

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId, message }),
      });
      const data = await res.json();
      if (awaitingResponse && data && typeof data.assistantMessage === 'string') {
        addMessage(data.assistantMessage, 'agent');
        awaitingResponse = false;
        hideTyping();
      }
    } catch (err) {
      hideTyping();
      awaitingResponse = false;
      showToolPopup('error', { message: 'Failed to send. Check server.' });
    }
  });
})();


