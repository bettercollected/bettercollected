# The Pigment theme preset

Pigment is a theme preset next to Default, Leaflet, Kantlijn, Daybreak and the others:
iris on warm cream paper, a sun-yellow band over the questions, lettered answer keys in
five flat colours, and five flat shapes that pop around the check when the form is sent.
Creators opt into it in the form builder's Design tab (or an edit operation, the AI
assistant or the MCP server sets it by name). It is **not** the preset new forms start
with; that is `NEW_FORM_THEME` in `backend/backend/app/constants/themes.py` (and
`NEW_FORM_THEME_TITLE` in `webapp/src/constants/theme.ts`), still Leaflet, also in a
workspace that chose the Pigment app theme.

It is behind the switch of the second app theme, `APP_THEME_PIGMENT_ENABLED` (see
`docs/app-theme.md` and `docs/settings-inventory.md`). There is no switch of its own: one
switch covers the workspace appearance choice and this preset.

## What it is

A preset is a theme stored inline on the form. Pigment is

| Key | Value |
|---|---|
| `primary` (questions, text, answers) | `#1A1238` |
| `secondary` (buttons, progress, the chosen option, the focus ring) | `#4B35DB` (iris) |
| `tertiary` (input edges) | `#7C7396` |
| `accent` (the page) | `#FBF7F1` (cream) |
| `style` | `classic` |
| `choiceKeys` | `letters` (see the choice keys below) |
| `background` | `{ "type": "color", "artwork": "pigment" }` |

Faces, corners, button style, highlight and selection are left to the form, as the colour
presets do: picking Pigment over another preset keeps the form's own type and shape. The
`pigment` artwork is a scene the webapp draws itself
(`webapp/src/views/molecules/theme/pigment-art.tsx`): flat shapes in inline SVG and CSS,
no image file, no request to anyone, static. It adds no theme key of its own.

- **The band.** On a question page the header bar (Back, the organisation's chip, the page
  count) is sun-yellow `#FFC62E` with the form's ink on it, 11.3:1. The progress line stays
  iris. The comp's band is the one piece the existing header and background keys could not
  carry (the header's ground is derived from the page colour, and no key names it), so the
  scene draws it: no new key was needed.
- **Choice keys.** Each option of a choice question carries a small square with its letter
  (A, B, C, ...) in ink on a flat pigment: tomato, sun, mint, sky, orchid, then again. The
  chosen option is solid iris with white text (7.4:1) and a check at its end. The pigments
  are constants of the form (`CHOICE_KEY_FILLS` in `views/atoms/choice.tsx`); a respondent
  page never reads the app's colour variables.
- **"Why we ask this".** The rule beside the note is the tomato deepened to `#D44A33`,
  4.1:1 on the cream page (the plain tomato is 2.4:1). The focus ring and the chosen option
  stay iris.
- **The ending.** The band along the top of an ending without a picture half is sun-yellow
  with an iris disc that holds the check in white, and five flat shapes around it: circle
  (tomato), square (sky), triangle (mint), half-circle (orchid) and ring (ink). They pop in
  once, staggered over 0.7 s (80 ms apart, 360 ms each, with a little overshoot), then rest.
  Under `prefers-reduced-motion` they are simply placed, which is also where the animation
  ends. CSS and inline SVG only, no sound, no confetti. The picture is a 320 by 160 box
  centred in a band 150 px tall on a phone (drawn at 256 by 128) and 200 px from `sm`, so it
  has 11 to 20 px of yellow above and below it, and every shape is at least 8 units inside
  the box. The heading and sentence start directly under the band. The submission number
  stays in its white card and the trust strip stays neutral. A page set beside a picture keeps
  its picture and has no band.

## Colour is never the only signal

The five pigments sit behind ink letters, so **the letter carries the identity of an option,
not the colour**: someone who cannot tell the pigments apart reads the same A, B, C. The
chosen option is told by its solid fill, its bold text and its check, never by colour alone.
The key is decorative to assistive technology (`aria-hidden`); an option is still named by its
label. A letter shortcut works only as the option keys of other themes already do (a plain
letter, only on an option, never in a text field).

## Contrast

Every pair is held to the same rules as the other presets (the builder's contrast guard,
`services/theme_contrast.py`, `docs/spec/theme-contrast.cases.json`):

| Pair | Needs | Ratio |
|---|---|---|
| Questions and text on the page (`#1A1238` on `#FBF7F1`) | 4.5:1 | 16.6:1 |
| Answers in the white input boxes (`#1A1238` on white) | 4.5:1 | 17.7:1 |
| White on iris (button text, the chosen row, the check) | 4.5:1 | 7.4:1 |
| Iris on the page (progress, focus ring) | 3:1 | 7.0:1 |
| Input edge `#7C7396` on the page | 3:1 | 4.1:1 |
| Input edge on white | 3:1 | 4.4:1 |
| "Why we ask this" rule `#D44A33` on the page | 3:1 | 4.1:1 |
| Ink on the sun-yellow band | 4.5:1 | 11.3:1 |
| Key letter ink on tomato `#FF8A73` | 4.5:1 | 7.7:1 |
| Key letter ink on sun `#FFC62E` | 4.5:1 | 11.3:1 |
| Key letter ink on mint `#5FD9B0` | 4.5:1 | 10.1:1 |
| Key letter ink on sky `#6BBEF7` | 4.5:1 | 8.7:1 |
| Key letter ink on orchid `#D9A0FF` | 4.5:1 | 8.8:1 |

A key letter is the theme's `primary` where it holds 4.5:1 on its pigment, else black.

## The switch

`APP_THEME_PIGMENT_ENABLED` decides whether the preset's **name is offered**, exactly as
`DAYBREAK_PRESET_ENABLED` does for Daybreak (`docs/daybreak-preset.md`): the same
`GATED_PRESETS` and `GATED_ARTWORKS` (backend `constants/themes.py`, mirrored in
`webapp/src/constants/theme.ts`) name the setting, and the same checks run on every path
that takes a name or an inline theme.

- **Off (the default).** The picker and the Themes page do not list it
  (`offeredGatedPresets` of the permissions answer leaves it out); the edit operations, the
  AI outline, the AI's list of looks and the MCP server treat `Pigment` as an unknown preset;
  a new theme that names `background.artwork: "pigment"` is refused as an unlisted artwork is
  (422 `theme_not_allowed` or an operation error) in a whole-form save, a new form, `update_theme`,
  `update_page`, the one write path of the AI and MCP writers and a workspace's saved themes.
- **Stored values never depend on it.** A form that stores the preset, or the artwork at
  the same place of the stored form, renders, publishes and saves as before, and the builder
  keeps it in the picker as the form's current look. A copy of a form keeps what its source has.
- **On.** All of the above know the name.

## Where to look

- Backend: `backend/backend/app/constants/themes.py` (`theme_dict`, `GATED_PRESETS`,
  `GATED_ARTWORKS`), `services/form_themes.py` (the artwork gate).
- Webapp: `constants/theme.ts`, `views/molecules/theme/pigment-art.tsx`, `views/atoms/choice.tsx`
  (the keys), `views/organism/form/form-slide.tsx` (the band), `theme-artwork.tsx` (the ending).
- Tests: `backend/tests/app/services/test_pigment_preset.py`,
  `backend/tests/app/controllers/test_pigment_artwork_gate.py`,
  `webapp/src/views/molecules/theme/pigment.test.tsx`, and the shared cases in
  `docs/spec/form-ops-v1.cases.json` and `docs/spec/theme-contrast.cases.json`.
