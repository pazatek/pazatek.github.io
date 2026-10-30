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

  // Windows has no flag emoji and shows the letters "PL", so the drawn flag stays unless the
  // emoji actually renders as a flag (in color, unlike the letters).
  const flag = document.querySelector('.flag');
  if (flag) {
    const probe = document.createElement('canvas').getContext('2d', { willReadFrequently: true });
    probe.canvas.width = probe.canvas.height = 24;
    probe.font = '20px sans-serif';
    probe.fillText('🇵🇱', 0, 20);
    const pixels = probe.getImageData(0, 0, 24, 24).data;
    for (let i = 0; i < pixels.length; i += 4) {
      if (pixels[i + 3] > 128 && pixels[i] - pixels[i + 1] > 80) {
        flag.replaceWith('🇵🇱');
        break;
      }
    }
  }

  const markScrolled = () => root.classList.toggle('scrolled', scrollY > 40);
  addEventListener('scroll', markScrolled, { passive: true });
  markScrolled();

  const heroTitle = document.querySelector('.hero-text h1');
  if (heroTitle) {
    let stop = null;
    let previewing = false;
    Promise.all([
      fetch('handwriting.json').then(res => res.ok ? res.json() : Promise.reject(res.status)),
      import('./pen.js'),
    ])
      .then(([data, pen]) => { if (!previewing) stop = playHandwriting(heroTitle, data, pen); })
      .catch(() => { if (!previewing) root.classList.remove('hw'); });

    // The stroke editor in _draw/ embeds this page and sends unsaved edits to preview them in place.
    if (window.parent !== window) {
      addEventListener('message', async e => {
        if (e.origin !== location.origin) return;
        const { offset } = e.data ?? {};
        const placed = heroTitle.querySelector('.hero-handwriting');
        if (offset && placed) {
          placed.style.setProperty('--hw-x', offset.x);
          placed.style.setProperty('--hw-y', offset.y);
          return;
        }
        if (!e.data?.handwriting) return;
        previewing = true;
        const pen = await import('./pen.js');
        stop?.();
        root.classList.add('hw');
        stop = playHandwriting(heroTitle, e.data.handwriting, pen, { instant: e.data.instant });
      });
    }
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

  function playHandwriting(title, data, { prepareStroke, strokePath }, { instant = false } = {}) {
    const START_DELAY = 400;
    const SPEED = 2.8;
    // Pauses shrink on their own scale so word breaks still read longer than gaps between letters.
    const PAUSE_SCALE = 0.2;
    const PAUSE_CAP = 500;
    const EYE_RANGE = 11;

    const strokes = [];
    let clock = 0;
    let prevEnd = null;
    data.strokes.forEach((flat, n) => {
      const raw = [];
      for (let i = 0; i < flat.length; i += 4) raw.push([flat[i], flat[i + 1], flat[i + 3], flat[i + 2]]);
      const points = prepareStroke(raw);
      const start = raw[0][3];
      if (prevEnd !== null) clock += Math.min(Math.max(0, start - prevEnd), PAUSE_CAP) * PAUSE_SCALE;
      prevEnd = raw[raw.length - 1][3];
      strokes.push({ points, times: points.map(p => clock + (p[3] - start) / SPEED), weight: data.weight?.[n] ?? 1, path: null });
      clock += (prevEnd - start) / SPEED + (data.pauseAfter?.[n] ?? 0);
    });
    const duration = strokes[strokes.length - 1].times.slice(-1)[0];

    // The writing's lowest point is the tail of the "y", which can hang down across the line of text below.
    let tail = { stroke: 0, y: -Infinity };
    strokes.forEach(({ points }, n) => {
      for (const p of points) if (p[1] > tail.y) tail = { stroke: n, y: p[1] };
    });

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
    for (const eye of eyes) {
      eye.near = strokes
        .filter((stroke, n) => !data.eyes.includes(n))
        .flatMap(stroke => stroke.points)
        .filter(p => Math.hypot(p[0] - eye.x, p[1] - eye.y) < EYE_RANGE * 2 + 10);
    }

    // How far along (tx, ty) a pupil can go before it would touch another line: the gap covers the
    // pupil, the neighbouring ink and a margin, and never asks for more room than the pupil has at rest.
    function roomToLook(eye, tx, ty) {
      const closest = t => Math.min(...eye.near.map(p => Math.hypot(p[0] - eye.x - tx * t, p[1] - eye.y - ty * t)));
      const gap = Math.min(penSize * 1.7, closest(0));
      if (closest(1) >= gap) return 1;
      let lo = 0;
      let hi = 1;
      for (let i = 0; i < 8; i++) {
        const mid = (lo + hi) / 2;
        if (closest(mid) >= gap) lo = mid;
        else hi = mid;
      }
      return lo;
    }

    const canvas = document.createElement('canvas');
    canvas.className = 'hero-handwriting';
    canvas.setAttribute('aria-hidden', 'true');
    canvas.style.setProperty('--hw-aspect', data.width / data.height);
    canvas.style.setProperty('--hw-size', data.size ?? 1);
    canvas.style.setProperty('--hw-x', data.offset?.x ?? 0);
    canvas.style.setProperty('--hw-y', data.offset?.y ?? 0);
    title.appendChild(canvas);

    const ctx = canvas.getContext('2d');
    const ink = getComputedStyle(title.parentElement).color;
    let penSize = 1;
    let startedAt = null;
    // Arriving partway down the page (a link to a section, a reload mid-scroll) skips the replay.
    // Reduced motion doesn't: Windows sets it whenever "Animation effects" is off, and the writing
    // and the pupils move only within the heading.
    const skip = instant || scrollY > 0 || location.hash;
    let elapsed = skip ? Infinity : 0;
    const finished = () => {
      root.classList.add('hw-done');
      root.classList.remove('hw-playing');
    };
    if (skip) finished();
    else {
      root.classList.remove('hw-done');
      root.classList.add('hw-playing');
    }
    let stopped = false;
    const listeners = new AbortController();
    const signal = listeners.signal;

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

    // Make room for the tail where it crosses the line below: find the nearest space, then shift the
    // words on either side of it apart, on that line only, just far enough to clear the stroke. Word
    // positions depend on the font and how the line wraps (Windows uses a different system font), so
    // they're measured. Relative positioning moves the words without re-wrapping anything.
    const subtext = document.querySelector('.hero-subtext');
    function clearTailGap() {
      if (!subtext) return;
      for (const part of subtext.querySelectorAll('.hero-tail-push')) part.replaceWith(...part.childNodes);
      subtext.normalize();
    }

    function makeRoomForTail() {
      clearTailGap();
      const rect = canvas.getBoundingClientRect();
      const node = subtext?.firstChild;
      if (!rect.width || node?.nodeType !== Node.TEXT_NODE) return;
      const k = rect.width / data.width;
      const path = strokes[tail.stroke].points.map(p => [rect.left + p[0] * k, rect.top + p[1] * k]);
      const style = getComputedStyle(subtext);
      const em = parseFloat(style.fontSize);
      // Measured before the text fades in, while it's still lowered for its entrance; the tail slants,
      // so the crossing is found at the line's final height.
      const lowered = style.transform === 'none' ? 0 : new DOMMatrixReadOnly(style.transform).m42;
      const ink = parseFloat(getComputedStyle(title).fontSize) * 0.1 * (data.size ?? 1);
      const clearance = ink / 2 + em * 0.3;
      const range = document.createRange();
      const box = i => {
        range.setStart(node, i);
        range.setEnd(node, i + 1);
        return range.getBoundingClientRect();
      };

      let best = null;
      for (let i = node.data.indexOf(' '); i > 0 && i < node.data.length - 1; i = node.data.indexOf(' ', i + 1)) {
        const before = box(i - 1);
        const after = box(i + 1);
        if (after.top > before.bottom) continue;
        const middle = before.top + before.height / 2 - lowered;
        const crossing = path.reduce((a, b) => Math.abs(b[1] - middle) < Math.abs(a[1] - middle) ? b : a);
        if (Math.abs(crossing[1] - middle) > before.height / 2) continue;
        const left = Math.min(0, crossing[0] - clearance - before.right);
        const right = Math.max(0, crossing[0] + clearance - after.left);
        const cost = right - left;
        if (cost <= em * 1.5 && (!best || cost < best.cost)) best = { i, left, right, cost, top: before.top };
      }
      if (!best || !best.cost) return;

      let start = best.i;
      let end = best.i;
      while (start > 0 && Math.abs(box(start - 1).top - best.top) < 1) start--;
      while (end < node.data.length - 1 && Math.abs(box(end + 1).top - best.top) < 1) end++;
      node.splitText(end + 1);
      const after = node.splitText(best.i + 1);
      node.splitText(best.i);
      const before = node.splitText(start);
      for (const [part, offset] of [[before, best.left], [after, best.right]]) {
        if (!offset) continue;
        const push = document.createElement('span');
        push.className = 'hero-tail-push';
        push.style.left = `${offset}px`;
        part.replaceWith(push);
        push.append(part);
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
        const room = roomToLook(eye, vx / dist * reach, vy / dist * reach);
        eye.tx = vx / dist * reach * room;
        eye.ty = vy / dist * reach * room;
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
      if (settling && !stopped) requestAnimationFrame(glance);
      else gazing = false;
    }

    if (eyes.length) {
      document.addEventListener('pointermove', e => {
        if (e.pointerType === 'touch') return;
        pointer = { x: e.clientX, y: e.clientY };
        aim();
      }, { passive: true, signal });
      document.addEventListener('mouseout', e => {
        if (e.relatedTarget) return;
        pointer = null;
        aim();
      }, { signal });
      addEventListener('scroll', aim, { passive: true, signal });
    }

    function frame(now) {
      if (startedAt === null) startedAt = now + START_DELAY;
      elapsed = Math.max(0, now - startedAt);
      render();
      if (elapsed >= duration) finished();
      else if (!stopped) requestAnimationFrame(frame);
    }

    const resizer = new ResizeObserver(([entry]) => {
      const dpr = window.devicePixelRatio || 1;
      const cssWidth = entry.contentRect.width;
      // The exact device-pixel size keeps the ink as crisp as the type; Safari doesn't report it.
      const device = entry.devicePixelContentBoxSize?.[0];
      canvas.width = device ? device.inlineSize : Math.round(cssWidth * dpr);
      canvas.height = device ? device.blockSize : Math.round(entry.contentRect.height * dpr);
      // Ink weight follows the heading size, not the recording's scale, so it reads like the type it replaces.
      penSize = parseFloat(getComputedStyle(title).fontSize) * 0.1 * (data.size ?? 1) * data.width / cssWidth;
      strokes.forEach(stroke => { stroke.path = null; });
      render();
      makeRoomForTail();
    });
    resizer.observe(canvas);
    document.fonts?.ready.then(() => { if (!stopped) makeRoomForTail(); });

    if (elapsed === 0) requestAnimationFrame(frame);

    return () => {
      stopped = true;
      listeners.abort();
      resizer.disconnect();
      canvas.remove();
      clearTailGap();
    };
  }

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => entry.target.classList.toggle('is-offscreen', !entry.isIntersecting));
    }, { rootMargin: '10% 0px' });
    document.querySelectorAll('.project').forEach(project => observer.observe(project));
  }
});
