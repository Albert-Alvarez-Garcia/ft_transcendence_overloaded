(async () => {
  const $ = (id) => document.getElementById(id);
  const user = await api.requireSession();
  if (!user) return;

  const CLOSE_TEXT = {
    4404: 'La sala no existe o ha caducado.', 4410: 'La partida ya ha empezado.',
    4411: 'La sala está llena.', 4409: 'Has abierto esta sala en otra pestaña.'
  };
  const ERR_TEXT = {
    not_host: 'Solo el anfitrión puede empezar.', not_enough_players: 'Faltan jugadores.',
    already_started: 'La partida ya ha empezado.', not_playing: 'La partida no está en marcha.',
    too_fast: 'Vas demasiado rápido.', unknown_type: 'Mensaje no válido.',
    bad_message: 'Mensaje no válido.', too_large: 'Mensaje demasiado grande.'
  };
  let client = null;
  let state = null;

  function say(el, text, isError) {
    el.textContent = text;
    el.className = 'msg' + (isError ? ' err' : '');
  }

  function li(text) {
    const item = document.createElement('li');
    item.textContent = text;
    return item;
  }

  // ---- lobby ----
  async function loadGames() {
    const r = await api.get('/api/games');
    if (!r.ok) { say($('lobby-msg'), api.text(r.error), true); return; }
    $('game').replaceChildren(...r.games.map((g) => {
      const o = document.createElement('option');
      o.value = g.id;
      o.textContent = g.name + ' (' + g.minPlayers + '-' + g.maxPlayers + ')';
      return o;
    }));
  }

  async function loadRooms() {
    const r = await api.get('/api/rooms');
    if (!r.ok) { say($('lobby-msg'), api.text(r.error), true); return; }
    $('rooms').replaceChildren(...(r.rooms.length ? r.rooms.map((room) => {
      const item = li(room.code + ' · ' + room.game + ' · ' + room.players + '/' + room.maxPlayers + ' · ' + room.host + ' ');
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = 'Unirse';
      b.addEventListener('click', () => join(room.code));
      item.appendChild(b);
      return item;
    }) : [li('No hay salas abiertas.')]));
  }

  async function join(code) {
    const clean = String(code).trim().toUpperCase();
    const r = await api.get('/api/rooms/' + encodeURIComponent(clean));
    if (!r.ok) { say($('lobby-msg'), api.text(r.error), true); return; }
    enter(clean);
  }

  $('create').addEventListener('click', async () => {
    const r = await api.post('/api/rooms', { game: $('game').value });
    if (!r.ok) { say($('lobby-msg'), api.text(r.error), true); return; }
    enter(r.code);
  });
  $('join-form').addEventListener('submit', (e) => { e.preventDefault(); join($('code').value); });
  $('refresh').addEventListener('click', loadRooms);

  // ---- sala ----
  function enter(code) {
    $('lobby-view').hidden = true;
    $('room-view').hidden = false;
    $('log').replaceChildren();
    say($('room-msg'), '', false);
    client = new RoomClient(code, { message: onMessage, close: onClose });
    client.connect();
  }

  function backToLobby(text, isError) {
    client = null;
    state = null;
    $('room-view').hidden = true;
    $('lobby-view').hidden = false;
    say($('lobby-msg'), text || '', isError);
    loadRooms();
  }

  function onClose(code) {
    if (client) backToLobby(CLOSE_TEXT[code] || '', Boolean(CLOSE_TEXT[code]));
  }

  function addLine(text, cls) {
    const p = document.createElement('p');
    if (cls) p.className = cls;
    p.textContent = text;
    $('log').appendChild(p);
    $('log').scrollTop = $('log').scrollHeight;
  }

  function nameOf(id) {
    const p = state.players.find((x) => String(x.id) === String(id));
    return p ? p.username : id;
  }

  function onMessage(m) {
    if (m.type === 'room_state') { state = m; render(); return; }
    if (!state) return;
    switch (m.type) {
      case 'player_joined':
        state.players.push(m.player);
        addLine(m.player.username + ' ha entrado', 'sys');
        break;
      case 'player_left':
        state.players = state.players.filter((p) => p.id !== m.id);
        state.hostId = m.hostId;
        break;
      case 'player_status': {
        const p = state.players.find((x) => x.id === m.id);
        if (p) p.connected = m.connected;
        break;
      }
      case 'phase': state.phase = m.phase; state.endsAt = m.endsAt; break;
      case 'chat': addLine(m.user + ': ' + m.text); break;
      case 'game':
        if (m.action === 'progress') state.gameState.clicks = m.clicks;
        break;
      case 'finished': state.phase = 'finished'; state.results = m.results; break;
      case 'error': say($('room-msg'), ERR_TEXT[m.code] || m.code, true); return;
      default: return;
    }
    render();
  }

  function render() {
    $('room-code').textContent = state.code;
    $('players').replaceChildren(...state.players.map((p) =>
      li(p.username + (p.id === state.hostId ? ' (anfitrión)' : '') + (p.connected ? '' : ' — desconectado'))));
    const isHost = state.you.id === state.hostId;
    $('start').hidden = !(isHost && state.phase !== 'playing');
    $('start').textContent = state.phase === 'finished' ? 'Jugar otra vez' : 'Empezar';
    $('game-area').hidden = state.phase === 'lobby';
    $('click').hidden = state.phase !== 'playing';
    const gs = state.gameState || {};
    $('progress').replaceChildren(...Object.entries(gs.clicks || {}).map(([id, n]) =>
      li(nameOf(id) + ': ' + n + ' / ' + gs.target)));
    $('results').replaceChildren(...(state.phase === 'finished' && state.results
      ? state.results.map((r) => li(r.rank + '. ' + r.username + ' (' + r.score + ')')) : []));
  }

  $('start').addEventListener('click', () => client && client.start());
  $('click').addEventListener('click', () => client && client.game('click'));
  $('leave').addEventListener('click', () => { if (client) client.leave(); });
  $('chat-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const text = $('chat-input').value.trim();
    if (text && client) { client.chat(text); $('chat-input').value = ''; }
  });

  loadGames();
  loadRooms();
})();
