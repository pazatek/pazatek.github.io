document.addEventListener('DOMContentLoaded', () => {
  const root = document.documentElement;

  // Load the inactive theme's hero image once the page is idle, so the
  // day/night crossfade has both layers ready without blocking first paint.
  const loadBothHeroImages = () => root.classList.add('hero-both');
  const scheduleHeroPrefetch = () => {
    if ('requestIdleCallback' in window) requestIdleCallback(loadBothHeroImages, { timeout: 3000 });
    else setTimeout(loadBothHeroImages, 1500);
  };
  if (document.readyState === 'complete') scheduleHeroPrefetch();
  else window.addEventListener('load', scheduleHeroPrefetch, { once: true });

  // Day/night theme toggle (persists override to localStorage; default is system pref)
  const heroToggle = document.getElementById('hero-toggle');
  const themeColor = document.querySelector('meta[name="theme-color"]');

  if (heroToggle) {
    heroToggle.setAttribute('aria-pressed', root.classList.contains('dark'));

    heroToggle.addEventListener('click', () => {
      loadBothHeroImages();
      document.body.classList.add('theme-transition');
      const isDark = root.classList.toggle('dark');

      heroToggle.setAttribute('aria-pressed', isDark);
      if (themeColor) themeColor.content = isDark ? '#18181b' : '#fafafa';
      try { localStorage.setItem('theme', isDark ? 'dark' : 'light'); } catch (e) {}

      setTimeout(() => document.body.classList.remove('theme-transition'), 900);
    });
  }

  // Copy email
  const copyBtn = document.getElementById('copy-email');
  const emailLabel = document.getElementById('email-label');
  if (copyBtn && emailLabel) {
    copyBtn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(copyBtn.dataset.copy);
        emailLabel.textContent = 'Copied!';
        copyBtn.classList.add('copied');
        setTimeout(() => {
          emailLabel.textContent = 'Email';
          copyBtn.classList.remove('copied');
        }, 1200);
      } catch (err) {
        console.error('Failed to copy:', err);
      }
    });
  }

  // h2c calendar — populate next week's dates
  const today = new Date();
  const dayOfWeek = today.getDay(); // 0=Sun, 1=Mon...
  const daysUntilNextMon = dayOfWeek === 0 ? 1 : 8 - dayOfWeek;
  const nextMon = new Date(today);
  nextMon.setDate(today.getDate() + daysUntilNextMon);

  const ids = ['h2c-mon-num', 'h2c-tue-num', 'h2c-wed-num', 'h2c-thu-num', 'h2c-fri-num'];
  ids.forEach((id, i) => {
    const el = document.getElementById(id);
    if (el) {
      const d = new Date(nextMon);
      d.setDate(nextMon.getDate() + i);
      el.textContent = d.getDate();
    }
  });

  // PII redaction demo
  const shieldBtn = document.getElementById('shield-toggle');
  const statusLabel = document.getElementById('shield-status');
  const redactables = document.querySelectorAll('.pii-redactable');

  if (shieldBtn && statusLabel && redactables.length) {
    shieldBtn.addEventListener('click', () => {
      const active = shieldBtn.classList.toggle('active');
      shieldBtn.setAttribute('aria-pressed', active);
      statusLabel.textContent = active ? 'On' : 'Off';

      redactables.forEach(el => {
        el.classList.toggle('redacted', active);
        el.textContent = active ? el.dataset.redacted : el.dataset.original;
      });
    });
  }

  // Pause looping demo animations in cards that are scrolled out of view
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => entry.target.classList.toggle('is-offscreen', !entry.isIntersecting));
    }, { rootMargin: '10% 0px' });
    document.querySelectorAll('.project-card').forEach(card => observer.observe(card));
  }
});
