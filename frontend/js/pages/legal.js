// Selector de idioma de las páginas legales (inglés por defecto; ?lang=es abre en español).
(() => {
  const buttons = document.querySelectorAll('[data-lang]');

  function setLang(lang) {
    document.querySelectorAll('section[lang]').forEach((s) => { s.hidden = s.lang !== lang; });
    document.documentElement.lang = lang;
    buttons.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.lang === lang)));
  }

  buttons.forEach((b) => b.addEventListener('click', () => setLang(b.dataset.lang)));
  setLang(new URLSearchParams(location.search).get('lang') === 'es' ? 'es' : 'en');
})();
