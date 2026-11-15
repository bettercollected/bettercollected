# The Daybreak theme preset

Daybreak is a theme preset next to Default, Leaflet, Kantlijn and the others: the
blue of the Default preset on a soft periwinkle page, with a small flat sun and
two hills as its only illustration. Creators opt into it in the form builder's
Design tab (or an edit operation, the AI assistant or the MCP server sets it by
name). It is **not** the preset new forms start with; that is
`NEW_FORM_THEME` in `backend/backend/app/constants/themes.py` (and
`NEW_FORM_THEME_TITLE` in `webapp/src/constants/theme.ts`), still Leaflet.

It is behind the server switch `DAYBREAK_PRESET_ENABLED` (off by default; see
`docs/settings-inventory.md`).

## What it is

A preset is a theme stored inline on the form. Daybreak is

| Key | Value |
|---|---|
| `primary` (questions, text, answers) | `#0E1737` |
| `secondary` (buttons, chosen answer, progress, focus ring) | `#1649E2`, the Default preset's blue |
| `tertiary` (input edges) | `#6E7CA8` |
| `accent` (the page) | `#F3F6FF` |
| `style` | `classic` |
| `background` | `{ "type": "color", "artwork": "daybreak" }` |

Faces, corners, button style, highlight and selection are left to the form: picking
Daybreak over another preset keeps the form's own type and shape, as the colour
presets do. The artwork is `background.artwork: "daybreak"`, a scene the webapp draws
itself (`webapp/src/views/molecules/theme/daybreak-art.tsx`): flat shapes in inline
SVG, no image file, no request to anyone, static.

- **Corner sun.** A pale quarter disc with the sun inside it, in the top right
  corner of every page, painted as the page's background image so it sits under
  the questions and does not scroll. Its size follows the page (130 to 260 px).
- **"Why we ask this".** The rule beside the note is the sun deepened to
  `#B07400`, 3.6:1 on the page (the bright sun, 1.7:1, would not pass the 3:1 rule for
  non-text marks). The focus ring and the chosen answer stay in the action blue.
- **The ending.** The band along the top of an ending without a picture half: a
  sun rises behind two hills for one second (ease-out), then a check draws itself
  inside it (half a second, after the rise). It plays once, when the ending
  appears. With `prefers-reduced-motion` the finished picture is shown, with no
  motion. No confetti, no sound. The submission number stays in its white card and
  the trust strip stays neutral. A page set beside a picture keeps its picture and
  has no band.

The artwork is not a picture artwork: it never fills a welcome or ending page's
picture half and never changes a page's layout (`PICTURE_ARTWORKS` in both
`constants/themes.py` and `constants/theme.ts`; only `marble` is one).

## Contrast

Every pair is held to the same rules as the other presets (the builder's
contrast guard, `services/theme_contrast.py`, `docs/spec/theme-contrast.cases.json`):

| Pair | Needs | Ratio |
|---|---|---|
| Questions and text on the page (`#0E1737` on `#F3F6FF`) | 4.5:1 | 16.3:1 |
| Answers in the white input boxes (`#0E1737` on white) | 4.5:1 | 17.6:1 |
| Button text (white on `#1649E2`) | 4.5:1 | 6.8:1 |
| Action blue on the page (chosen answer, progress, focus ring) | 3:1 | 6.3:1 |
| Input edge on the page (`#6E7CA8` on `#F3F6FF`) | 3:1 | 3.8:1 |
| Input edge on white | 3:1 | 4.1:1 |
| "Why we ask this" rule (`#B07400` on `#F3F6FF`) | 3:1 | 3.6:1 |
| Ink on the sun (`#0E1737` on `#FFB400`, the check) | 4.5:1 | 9.9:1 |

## The switch

`DAYBREAK_PRESET_ENABLED` decides whether the preset's **name is offered**:

- **Off (the default).** The builder's Design tab and the workspace Themes page do
  not list it (the permissions answer's `offeredGatedPresets` is empty); the edit
  operations (`set_theme_preset`), the outline the AI writes, the AI's list of looks and
  the MCP server treat `Daybreak` as an unknown preset: the same refusal, and the
  list in the message leaves it out. Nothing else changes.
- **Stored values never depend on it.** A form that stores the theme renders it,
  publishes and saves as before, and the builder keeps it in the picker as the
  form's current look. A theme sent inline with `artwork: "daybreak"` is valid
  whatever the switch says: the artwork is a stored-value vocabulary like `marble`.
- **On.** All of the above know the name.

`GATED_PRESETS` (`backend/backend/app/constants/themes.py`, mirrored in
`webapp/src/constants/theme.ts`; a test keeps them together) maps each preset that has
a switch to its setting. A later preset with its own switch joins that list; the
picker, the edit engine (`offeredGatedPresets` in its options) and `preset_name` need
no other change.

## Where to look

- Backend: `backend/backend/app/constants/themes.py` (`theme_dict`, `GATED_PRESETS`,
  `preset_offered`, `offered_presets`, `preset_name`), `ops.py` `set_theme_preset`.
- Webapp: `constants/theme.ts`, `views/molecules/theme/daybreak-art.tsx`,
  `theme-shared.tsx` (`themeBackgroundStyle`), `theme-root.ts` (the rule),
  `theme-artwork.tsx` (the band), `views/organism/form-builder/page-design-tab.tsx`.
- Tests: `backend/tests/app/services/test_daybreak_preset.py`,
  `test_theme_pins.py` (what existing presets and forms with no theme draw, pinned),
  `webapp/src/views/molecules/theme/daybreak.test.tsx`, `theme-pins.test.tsx`, and the
  shared cases in `docs/spec/form-ops-v1.cases.json` and
  `docs/spec/theme-contrast.cases.json`.
