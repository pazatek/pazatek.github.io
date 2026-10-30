# piotrzatek.com

Static personal site served by GitHub Pages from `main`. Plain HTML, CSS and JS: no build step. The one library, perfect-freehand (pen strokes for the handwritten hero), is vendored in `vendor/`.

- Preview locally with `python3 -m http.server` and check both themes and a phone-width viewport.
- `styles.css` and `script.js` are linked with `?v=N` (in `index.html` and `privacy/index.html`); bump N whenever either changes. GitHub Pages lets browsers cache them for 10 minutes, and a stale copy paired with new HTML breaks the page.
- Colors live as tokens in `:root` / `:root.dark` in `styles.css`; don't hardcode new ones.
- Hero images are chosen in two places that must agree: the preload script in `index.html` and the 640px media query in `styles.css`.
- The hero title is a handwriting replay of `handwriting.json`, recorded on an iPad via `python3 _draw/serve.py` and `/_draw/`, and touched up stroke by stroke in `/_draw/edit.html`. GitHub Pages' Jekyll build skips `_`-prefixed folders, so the recorder isn't published.
- `eyes`, `head`, `face`, `nose`, `weight` and `pauseAfter` in `handwriting.json` point at strokes by index: pupils that follow the cursor, the strokes that turn with the head, the features that move together as one face, the strokes that stick out from it, strokes drawn lighter, and extra milliseconds of replay pause after a stroke. `size` scales the whole drawing on the page and `offset` moves it, both in units of the heading's font size. The editor renumbers them when strokes are deleted; hand edits to the stroke list must too.
- Don't add Microsoft's Michelangelus font files: its EULA grants no redistribution rights.

## Comments

Comments explain *why*, never *what*. Keep one only when deleting it would let someone plausibly break something (a browser quirk, a performance constraint, two places that must stay in sync). Don't label sections or restate the code.

Never annotate a workaround or hack with a comment. Fix the underlying problem instead, or leave it as is and raise it with the user.
