document.addEventListener('DOMContentLoaded', () => {
  // Match subtext width to heading
  const heading = document.querySelector('.hero-heading');
  const subtext = document.querySelector('.hero-subtext');

  function matchWidth() {
    if (heading && subtext) subtext.style.maxWidth = (heading.offsetWidth + 80) + 'px';
  }
  matchWidth();

  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(matchWidth, 150);
  });

  // AVIF support detection
  function supportsAvif() {
    return new Promise(resolve => {
      const img = new Image();
      img.onload = () => resolve(true);
      img.onerror = () => resolve(false);
      img.src = 'data:image/avif;base64,AAAAIGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZk1BMUIAAADybWV0YQAAAAAAAAAoaGRscgAAAAAAAAAAcGljdAAAAAAAAAAAAAAAAGxpYmF2aWYAAAAADnBpdG0AAAAAAAEAAAAeaWxvYwAAAABEAAABAAEAAAABAAABGgAAAB0AAAAoaWluZgAAAAAAAQAAABppbmZlAgAAAAABAABhdjAxQ29sb3IAAAAAamlwcnAAAABLaXBjbwAAABRpc3BlAAAAAAAAAAIAAAACAAAAEHBpeGkAAAAAAwgICAAAAAxhdjFDgQ0MAAAAABNjb2xybmNseAACAAIAAYAAAAAXaXBtYQAAAAAAAAABAAEEAQKDBAAAACVtZGF0EgAKBzgABpAgEAwgMgyfRAAAAAAAUAAABXQ=';
    });
  }

  // Hero images — set day image immediately, defer night image
  const dayEl = document.querySelector('.hero-image-day');
  const nightEl = document.querySelector('.hero-image-night');
  let nightImageLoaded = false;

  async function setHeroImages() {
    const avif = await supportsAvif();
    const ext = avif ? 'avif' : 'webp';

    if (dayEl) dayEl.style.backgroundImage = `url("images/valley.${ext}")`;

    // Store night image path for lazy loading on toggle
    if (nightEl) nightEl.dataset.bg = `url("images/valley-night.${ext}")`;
  }

  setHeroImages();

  // Day/night hero toggle
  const heroContainer = document.getElementById('hero-section');
  const heroToggle = document.getElementById('hero-toggle');
  const themeColor = document.querySelector('meta[name="theme-color"]');

  if (heroToggle && heroContainer) {
    heroToggle.addEventListener('click', () => {
      // Lazy-load night image on first toggle
      if (!nightImageLoaded && nightEl && nightEl.dataset.bg) {
        nightEl.style.backgroundImage = nightEl.dataset.bg;
        nightImageLoaded = true;
      }

      document.body.classList.add('theme-transition');
      heroContainer.classList.toggle('night');
      document.documentElement.classList.toggle('dark');

      const isDark = document.documentElement.classList.contains('dark');
      if (themeColor) themeColor.content = isDark ? '#18181b' : '#fafafa';

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
});
