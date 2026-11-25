// Cliente WebSocket de las salas (lo usan todas las páginas de juego). Contrato: docs/WS.md
(() => {
  class RoomClient {
    // handlers: { message(m), close(code) }
    constructor(code, handlers) {
      this.code = code;
      this.on = handlers || {};
      this.ws = null;
    }

    connect() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      this.ws = new WebSocket(proto + '://' + location.host + '/ws/rooms/' + encodeURIComponent(this.code));
      this.ws.onmessage = (ev) => {
        let m;
        try { m = JSON.parse(ev.data); } catch (e) { return; }
        if (m && typeof m.type === 'string' && this.on.message) this.on.message(m);
      };
      this.ws.onclose = (ev) => {
        if (ev.code === 4401) { location.replace('/login.html'); return; }
        if (this.on.close) this.on.close(ev.code);
      };
    }

    send(type, data) {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify(Object.assign({ type }, data || {})));
      }
    }

    game(action, data) { this.send('game', Object.assign({ action }, data || {})); }
    chat(text) { this.send('chat', { text }); }
    start() { this.send('start'); }
    leave() { this.send('leave'); }
  }

  window.RoomClient = RoomClient;
})();
