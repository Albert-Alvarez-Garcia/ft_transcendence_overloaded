(async () => {
  const $ = (id) => document.getElementById(id);
  const user = await api.requireSession();
  if (!user) return;
  $('who').textContent = user.username;
  $('logout').addEventListener('click', () => api.logout());

  const log = $('log');
  const status = $('chat-status');
  let ws = null;

  function addLine(m) {
    const p = document.createElement('p');
    if (m.ts) {
      const t = document.createElement('time');
      t.textContent = new Date(m.ts * 1000).toLocaleTimeString();
      p.appendChild(t);
    }
    if (m.type === 'message') {
      const b = document.createElement('strong');
      b.textContent = m.user + ': ';
      p.appendChild(b);
      p.appendChild(document.createTextNode(m.text));
    } else {
      p.className = 'sys';
      p.appendChild(document.createTextNode(m.text));
    }
    log.appendChild(p);
    log.scrollTop = log.scrollHeight;
  }

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(proto + '://' + location.host + '/ws/chat');
    ws.onopen = () => { status.textContent = 'Conectado al chat.'; $('reconnect').hidden = true; };
    ws.onmessage = (ev) => {
      let m;
      try { m = JSON.parse(ev.data); } catch (e) { return; }
      if (m && typeof m.text === 'string') addLine(m);
    };
    ws.onclose = (ev) => {
      if (ev.code === 4401) { location.replace('/login.html'); return; }
      status.textContent = 'Desconectado del chat.';
      $('reconnect').hidden = false;
    };
  }

  $('chat-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const input = $('chat-input');
    const text = input.value.trim();
    if (text && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(text);
      input.value = '';
    }
  });
  $('reconnect').addEventListener('click', connect);
  connect();
})();
