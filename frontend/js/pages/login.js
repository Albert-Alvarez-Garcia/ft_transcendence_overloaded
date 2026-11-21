(async () => {
  const $ = (id) => document.getElementById(id);
  const msg = $('msg');
  const resend = $('resend');
  let lastEmail = '';

  function show(text, isError) {
    msg.textContent = text;
    msg.className = 'msg' + (isError ? ' err' : '');
  }

  function setTab(name) {
    const login = name === 'login';
    $('login-form').hidden = !login;
    $('register-form').hidden = login;
    $('tab-login').setAttribute('aria-selected', String(login));
    $('tab-register').setAttribute('aria-selected', String(!login));
    show('', false);
    resend.hidden = true;
  }

  $('tab-login').addEventListener('click', () => setTab('login'));
  $('tab-register').addEventListener('click', () => setTab('register'));

  const me = await api.get('/api/auth/me');
  if (me.authenticated) { location.replace('/home.html'); return; }

  const err = new URLSearchParams(location.search).get('error');
  if (err) show(api.text(err), true);

  $('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const identifier = String(f.get('identifier')).trim();
    const r = await api.post('/api/auth/login', { identifier, password: String(f.get('password')) });
    if (r.ok) { location.replace('/home.html'); return; }
    show(api.text(r.error), true);
    if (r.error === 'not_verified' && identifier.includes('@')) {
      lastEmail = identifier;
      resend.hidden = false;
    }
  });

  $('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const email = String(f.get('email')).trim();
    const r = await api.post('/api/auth/register', {
      username: String(f.get('username')).trim(), email, password: String(f.get('password'))
    });
    if (!r.ok) { show(api.text(r.error), true); return; }
    lastEmail = email;
    e.target.reset();
    setTab('login');
    show('Cuenta creada. Revisa tu correo para confirmarla.', false);
    resend.hidden = false;
  });

  resend.addEventListener('click', async () => {
    const r = await api.post('/api/auth/resend-verification', { email: lastEmail });
    show(r.ok ? 'Si el correo existe, te hemos enviado otro enlace.' : api.text(r.error), !r.ok);
  });
})();
