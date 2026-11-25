// Cliente de la API. Las respuestas esperadas (errores incluidos) llegan con HTTP 200 y {ok:false,error}.
(() => {
  const TEXT = {
    invalid_username: 'Usuario: 3-20 caracteres (letras, números, _ y -).',
    invalid_email: 'El correo no es válido.',
    invalid_password: 'La contraseña debe tener entre 8 y 72 caracteres.',
    username_taken: 'Ese nombre de usuario ya existe.',
    email_taken: 'Ese correo ya está registrado.',
    email_failed: 'No se pudo enviar el correo de confirmación. Inténtalo más tarde.',
    invalid_credentials: 'Usuario o contraseña incorrectos.',
    not_verified: 'Confirma tu correo antes de entrar.',
    too_many_attempts: 'Demasiados intentos. Espera unos minutos.',
    invalid_or_expired: 'El enlace no es válido o ha caducado.',
    unauthenticated: 'Tu sesión ha caducado.',
    already_exists: 'Ya existe: no se puede crear de nuevo.',
    not_created: 'Primero hay que crear el valor.',
    oauth_failed: 'No se pudo entrar con 42. Inténtalo de nuevo.',
    oauth_unavailable: 'El acceso con 42 no está configurado.',
    network: 'No hay conexión con el servidor.',
    unknown_game: 'Juego desconocido.',
    too_many_rooms: 'Hay demasiadas salas abiertas.',
    invalid_settings: 'Ajustes de sala no válidos.',
    room_not_found: 'La sala no existe o ha caducado.'
  };

  async function call(method, url, body) {
    try {
      const res = await fetch(url, {
        method,
        credentials: 'same-origin',
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined
      });
      return await res.json();
    } catch (e) {
      return { ok: false, error: 'network' };
    }
  }

  window.api = {
    get: (url) => call('GET', url),
    post: (url, body) => call('POST', url, body || {}),
    put: (url) => call('PUT', url),
    del: (url) => call('DELETE', url),
    text: (code) => TEXT[code] || 'Ha ocurrido un error.',
    async requireSession() {
      const r = await call('GET', '/api/auth/me');
      if (!r.authenticated) {
        location.replace('/login.html');
        return null;
      }
      return r.user;
    },
    async logout() {
      await call('POST', '/api/auth/logout', {});
      location.replace('/login.html');
    }
  };
})();
