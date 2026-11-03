# RecoverIQ deck

- `RecoverIQ_QUASAR5_Deck.pptx` — 21-slide deck (Round 0 content + Round 1 engineering slides + live demo script). Speaker notes on every slide.
- `RecoverIQ_QUASAR5_Deck.pdf` — PDF copy for upload.
- Before submitting: fill in the **Team** slide (names, colleges, photos). If QUASAR releases an official template, move the content into it.

Rebuild after editing `build_deck.js`:

```
npm install pptxgenjs@3.12.0
set NODE_PATH=%CD%\node_modules
set PPTX_SKILL=<path to the pptx skill folder>   (only needed for theme colours)
node build_deck.js
```
Screenshots in `img/` come from `recoveriq/backend/tests/e2e_ui.py`.
