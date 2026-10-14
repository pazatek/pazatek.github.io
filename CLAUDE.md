# piotrzatek.com

Static personal site served by GitHub Pages from `main`. Plain HTML, CSS and JS: no build step, no dependencies.

- Preview locally with `python3 -m http.server` and check both themes and a phone-width viewport.
- Colors live as tokens in `:root` / `:root.dark` in `styles.css`; don't hardcode new ones.
- Hero images are chosen in two places that must agree: the preload script in `index.html` and the 640px media query in `styles.css`.
- Don't add Microsoft's Michelangelus font files: its EULA grants no redistribution rights.

## Comments

Comments explain *why*, never *what*. Keep one only when deleting it would let someone plausibly break something (a browser quirk, a performance constraint, two places that must stay in sync). Don't label sections or restate the code.

Never annotate a workaround or hack with a comment. Fix the underlying problem instead, or leave it as is and raise it with the user.
