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

  const heroTitle = document.querySelector('.hero-text h1');
  if (heroTitle) {
    Promise.all([
      fetch('handwriting.json').then(res => res.ok ? res.json() : Promise.reject(res.status)),
      import('./pen.js'),
    ])
      .then(([data, pen]) => playHandwriting(heroTitle, data, pen))
      .catch(() => root.classList.remove('hw'));
  }

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
      } catch {
        location.href = 'mailto:' + copyBtn.dataset.copy;
      }
    });
  }

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

  function playHandwriting(title, data, { prepareStroke, strokePath }) {
    const START_DELAY = 400;
    const MAX_PAUSE = 120;
    const SPEED = 1.7;
    const EYE_RANGE = 4.5;

    const strokes = [];
    let shift = 0;
    let prevEnd = 0;
    data.strokes.forEach((flat, n) => {
      const raw = [];
      for (let i = 0; i < flat.length; i += 4) raw.push([flat[i], flat[i + 1], flat[i + 3], flat[i + 2]]);
      const points = prepareStroke(raw);
      shift += Math.max(0, raw[0][3] - prevEnd - MAX_PAUSE);
      prevEnd = raw[raw.length - 1][3];
      strokes.push({ points, times: points.map(p => (p[3] - shift) / SPEED), weight: data.weight?.[n] ?? 1, path: null });
    });
    const duration = strokes[strokes.length - 1].times.slice(-1)[0];

    const eyes = (data.eyes || []).filter(i => strokes[i]).map(i => {
      const { points } = strokes[i];
      const eye = {
        x: points.reduce((sum, p) => sum + p[0], 0) / points.length,
        y: points.reduce((sum, p) => sum + p[1], 0) / points.length,
        dx: 0, dy: 0, tx: 0, ty: 0,
      };
      strokes[i].eye = eye;
      return eye;
    });

    const canvas = document.createElement('canvas');
    canvas.className = 'hero-handwriting';
    canvas.setAttribute('aria-hidden', 'true');
    canvas.style.setProperty('--hw-aspect', data.width / data.height);
    title.appendChild(canvas);

    const ctx = canvas.getContext('2d');
    const ink = getComputedStyle(title.parentElement).color;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let penSize = 1;
    let startedAt = null;
    let elapsed = reduceMotion ? Infinity : 0;

    function render() {
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const scale = canvas.width / data.width;
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      ctx.fillStyle = ink;

      for (const stroke of strokes) {
        const { points, times, eye } = stroke;
        const size = penSize * stroke.weight;
        if (times[0] > elapsed) break;
        if (eye) ctx.translate(eye.dx, eye.dy);
        if (times[times.length - 1] <= elapsed) {
          ctx.fill(stroke.path ||= strokePath(points, size));
        } else {
          let shown = 1;
          while (times[shown] <= elapsed) shown++;
          ctx.fill(strokePath(points.slice(0, shown), size, false));
        }
        if (eye) ctx.translate(-eye.dx, -eye.dy);
      }
    }

    let pointer = null;
    let gazing = false;

    // Each pupil turns toward the cursor from its own position, so they converge a little when it's close.
    function aim() {
      const rect = canvas.getBoundingClientRect();
      if (rect.bottom < 0) return;
      const k = rect.width / data.width;
      for (const eye of eyes) {
        eye.tx = eye.ty = 0;
        if (!pointer) continue;
        const vx = pointer.x - (rect.left + eye.x * k);
        const vy = pointer.y - (rect.top + eye.y * k);
        const dist = Math.hypot(vx, vy) || 1;
        const reach = EYE_RANGE * (1 - Math.exp(-dist / 120));
        eye.tx = vx / dist * reach;
        eye.ty = vy / dist * reach;
      }
      if (!gazing) {
        gazing = true;
        requestAnimationFrame(glance);
      }
    }

    function glance() {
      let settling = false;
      for (const eye of eyes) {
        eye.dx += (eye.tx - eye.dx) * 0.18;
        eye.dy += (eye.ty - eye.dy) * 0.18;
        if (Math.abs(eye.tx - eye.dx) + Math.abs(eye.ty - eye.dy) > 0.02) settling = true;
        else { eye.dx = eye.tx; eye.dy = eye.ty; }
      }
      if (elapsed >= duration) render();
      if (settling) requestAnimationFrame(glance);
      else gazing = false;
    }

    if (eyes.length && !reduceMotion) {
      document.addEventListener('pointermove', e => {
        if (e.pointerType === 'touch') return;
        pointer = { x: e.clientX, y: e.clientY };
        aim();
      }, { passive: true });
      document.addEventListener('mouseout', e => {
        if (e.relatedTarget) return;
        pointer = null;
        aim();
      });
      addEventListener('scroll', aim, { passive: true });
    }

    function frame(now) {
      if (startedAt === null) startedAt = now + START_DELAY;
      elapsed = Math.max(0, now - startedAt);
      render();
      if (elapsed < duration) requestAnimationFrame(frame);
    }

    new ResizeObserver(([entry]) => {
      const dpr = window.devicePixelRatio || 1;
      const cssWidth = entry.contentRect.width;
      // The exact device-pixel size keeps the ink as crisp as the type; Safari doesn't report it.
      const device = entry.devicePixelContentBoxSize?.[0];
      canvas.width = device ? device.inlineSize : Math.round(cssWidth * dpr);
      canvas.height = device ? device.blockSize : Math.round(entry.contentRect.height * dpr);
      // Ink weight follows the heading size, not the recording's scale, so it reads like the type it replaces.
      penSize = parseFloat(getComputedStyle(title).fontSize) * 0.1 * data.width / cssWidth;
      strokes.forEach(stroke => { stroke.path = null; });
      render();
    }).observe(canvas);

    if (!reduceMotion) requestAnimationFrame(frame);
  }

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => entry.target.classList.toggle('is-offscreen', !entry.isIntersecting));
    }, { rootMargin: '10% 0px' });
    document.querySelectorAll('.project-card').forEach(card => observer.observe(card));
  }
});
