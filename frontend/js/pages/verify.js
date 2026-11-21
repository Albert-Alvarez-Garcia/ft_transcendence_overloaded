(async () => {
  const msg = document.getElementById('msg');
  const token = new URLSearchParams(location.search).get('token') || '';
  const r = token ? await api.post('/api/auth/verify-email', { token }) : { ok: false, error: 'invalid_or_expired' };
  msg.textContent = r.ok ? 'Correo confirmado. Ya puedes entrar.' : api.text(r.error);
  msg.className = 'msg' + (r.ok ? '' : ' err');
})();
