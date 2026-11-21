(async () => {
  const $ = (id) => document.getElementById(id);
  const user = await api.requireSession();
  if (!user) return;

  const CALLS = {
    create: () => api.post('/api/test'),
    read: () => api.get('/api/test'),
    update: () => api.put('/api/test'),
    delete: () => api.del('/api/test')
  };
  const OK_TEXT = { create: 'Creado: test = true.', read: 'Consultado.', update: 'Modificado.', delete: 'Borrado: test = null.' };

  function showValue(v) {
    $('value').textContent = v === null || v === undefined ? 'null (no creado)' : String(v);
  }

  async function refresh() {
    const r = await CALLS.read();
    if (r.error === 'unauthenticated') { location.replace('/login.html'); return; }
    if (r.ok) showValue(r.value);
  }

  document.querySelectorAll('[data-action]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const action = btn.dataset.action;
      const r = await CALLS[action]();
      if (r.error === 'unauthenticated') { location.replace('/login.html'); return; }
      $('msg').textContent = r.ok ? OK_TEXT[action] : api.text(r.error);
      $('msg').className = 'msg' + (r.ok ? '' : ' err');
      if (r.ok) showValue(r.value); else await refresh();
    });
  });

  refresh();
})();
