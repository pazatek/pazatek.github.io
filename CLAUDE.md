# piotrzatek.com

Static personal site served by GitHub Pages from `main`. Plain HTML, CSS and JS: no build step. The one library, perfect-freehand (pen strokes for the handwritten hero), is vendored in `vendor/`.

- Preview locally with `python3 -m http.server` and check both themes and a phone-width viewport.
- `styles.css`, `script.js` and `pen.js` are linked with `?v=N` (in `index.html`, `privacy/index.html` and the imports in `script.js`); bump N whenever any of them changes. GitHub Pages lets browsers cache them for 10 minutes, and a stale copy paired with new HTML breaks the page.
- Colors live as tokens in `:root` / `:root.dark` in `styles.css`; don't hardcode new ones.
- Hero images are chosen in two places that must agree: the preload script in `index.html` and the 640px media query in `styles.css`.
- The hero title is a handwriting replay of `handwriting.json`, recorded on an iPad via `python3 _draw/serve.py` and `/_draw/`, and touched up stroke by stroke in `/_draw/edit.html`. GitHub Pages' Jekyll build skips `_`-prefixed folders, so the recorder isn't published.
- `eyes`, `head`, `face`, `nose`, `swap`, `part`, `flip`, `ears`, `weight` and `pauseAfter` in `handwriting.json` point at strokes by index: pupils that follow the cursor, the strokes that move with the head, the features that tilt together as one face (the mouth moves less when the head looks down, so it stays off the jaw), then how each stroke becomes the drawing's mirror image as the head turns (the nose flips in place with its tip leading the turn, `swap` pairs trade places, `part` pairs do too but only partway, since those lines are the center part, not eyebrows, `flip` strokes also swap their ends, `ears` flatten onto the jaw while a mirrored copy opens out), strokes drawn at another weight, and extra milliseconds of replay pause after a stroke. `size` scales the whole drawing on the page and `offset` moves it, both in units of the heading's font size. The editor renumbers them when strokes are deleted; hand edits to the stroke list must too. Head strokes other than `eyes` render at one even pressure so the portrait keeps one line thickness; the editor's preview doesn't apply that.
- Don't add Microsoft's Michelangelus font files: its EULA grants no redistribution rights.

## Comments

Comments explain *why*, never *what*. Keep one only when deleting it would let someone plausibly break something (a browser quirk, a performance constraint, two places that must stay in sync). Don't label sections or restate the code.

Never annotate a workaround or hack with a comment. Fix the underlying problem instead, or leave it as is and raise it with the user.
