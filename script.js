document.addEventListener('DOMContentLoaded', () => {
  // Match subtext width to heading
  const heading = document.querySelector('.hero-heading');
  const subtext = document.querySelector('.hero-subtext');

  function matchWidth() {
    if (heading && subtext) subtext.style.maxWidth = (heading.offsetWidth + 13) + 'px';
  }
  matchWidth();
  window.addEventListener('resize', matchWidth);

  // Hero image pairs — randomly pick one per load
  const pairs = [
    { day: 'images/valley.webp', night: 'images/valley-night.webp', date: '08-01-2024' }
  ];

  const pick = pairs[Math.floor(Math.random() * pairs.length)];
  const dayEl = document.querySelector('.hero-image-day');
  const nightEl = document.querySelector('.hero-image-night');
  const creditEl = document.querySelector('.image-credit');

  if (dayEl) dayEl.style.backgroundImage = `url("${pick.day}")`;
  if (nightEl) nightEl.style.backgroundImage = `url("${pick.night}")`;
  if (creditEl) creditEl.textContent = `(original image taken by me on ${pick.date})`;

  // Day/night hero toggle
  const heroContainer = document.getElementById('hero-section');
  const heroToggle = document.getElementById('hero-toggle');

  if (heroToggle && heroContainer) {
    heroToggle.addEventListener('click', () => {
      document.body.classList.add('theme-transition');
      heroContainer.classList.toggle('night');
      document.documentElement.classList.toggle('dark');
      setTimeout(() => document.body.classList.remove('theme-transition'), 900);
    });
  }

  // Click to copy
  document.querySelectorAll('.contact-copyable').forEach(el => {
    el.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(el.dataset.copy);
        el.classList.add('copied');
        setTimeout(() => el.classList.remove('copied'), 1200);
      } catch (err) {
        console.error('Failed to copy:', err);
      }
    });
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
