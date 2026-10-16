# DESIGN.md

The design system of the bettercollected interface. bettercollected is a Sireto
product, and its interface reads as one: calm neutrals, one confident blue, flat
surfaces separated by hairlines, and nothing that pressures the person in front
of it.

This file is the reference the code cites (`DESIGN.md §n`). The values live in
one place, the `@theme` block of
[`webapp/src/assets/css/tailwind.css`](webapp/src/assets/css/tailwind.css); every
Tailwind utility (`bg-brand-500`, `text-body`, `rounded`, `shadow-large`, …) is
generated from it. When this document and the stylesheet disagree, fix one of
them. `webapp/src/assets/css/design-tokens.test.ts` checks the main rules.

**Scope.** This governs the app's own interface: dashboard, form builder, sign-in,
not-found and error pages, the responder portal, emails, and the "Powered by
bettercollected" badge. What respondents see inside a form is dressed by the
form's theme, which is the creator's choice (§9).

---

## 1. Colour

One blue ramp (`brand-*`) and one neutral ramp (`black-*`). Nothing else carries
product meaning; status colours (success, warning, danger) appear only where
they say something.

### Blue

| Token | Value | Role |
|---|---|---|
| `brand-100` | `#E0E8FF` | Blue tint: selected rows, chips, active-nav fill |
| `brand-200` | `#BFD0FF` | Blue soft: soft borders, secondary fills |
| `brand-500`, `brand` | `#123FC9` | Sireto blue: links, focus, active navigation, icons |
| `brand-600` | `#1035A8` | Text links, hover |
| `brand-700` | `#0E2D8F` | Pressed |
| `action` | `#1649E2` | Primary button face (6.8:1 with white text) |
| `action-hover` | `#123FC9` | Primary button, hover |
| `action-pressed` | `#0E2D8F` | Primary button, pressed; also its key edge |

`brand-300`, `brand-400`, `brand-800` and `brand-900` remain for the few
illustrations and charts that use them.

### Neutrals

| Token | Value | Role |
|---|---|---|
| `black-100` | `#F5F7FB` | Paper mist: the app background |
| `black-200` | `#F2F4F7` | Paper band: hover fills, table heads |
| `black-300` | `#EAECF0` | Hairline: edges and separators on white |
| `black-400` | `#D0D5DD` | Strong hairline: separators and dividers on paper mist, outlined-button edges |
| `black-500` | `#8A94A6` | Disabled text only — fails AA as text |
| `black-600` | `#667085` | Labels, captions, placeholders (4.6:1 on paper mist) |
| `black-700` | `#344054` | Emphasised body |
| `black-800` | `#27303F` | Dark surfaces (tooltips, secondary buttons) |
| `black-900`, `black` | `#101828` | Ink: headings, labels, answers |
| `body` | `#5A6478` | Running text (5.6:1 on paper mist) |
| `control` | `#818CA0` | Control edge: inputs, selects, checkboxes, radios, switch tracks |

**Control edge.** Anything you type into or toggle carries a `control` border
(3.2:1 on paper mist, 3.4:1 on white), so its boundary passes WCAG 1.4.11. A
hairline (`black-300`/`black-400`) is too faint to be the only sign that a
field is there; hairlines are for separating surfaces, not for controls.

### Accents and status

| Token | Value | Role |
|---|---|---|
| `brand-accent` | `#E5AE00` | Yellow, as a fill only (the Pro star, status dots) |
| `brand-accent-100` | `#FFF7DB` | Yellow tint behind olive text (pending, Pro) |
| `brand-olive` | `#8A6800` | Yellow-role text: yellow text on a light ground fails contrast |
| `success` | `#039855` | Success icons, fills and dots |
| `success-700` | `#027A48` | Success text (`success` is 3.7:1 on white, too light for text) |
| `#C43D3D` | — | Danger text and destructive buttons |

No pink, no orange, no gradients. The old bright blue (`#0764EB`), the old
trust blue (`#2456CC`) and the duplicate `new-*` ramps are gone.

## 2. Type

- **Faces.** [Instrument Sans](https://fonts.google.com/specimen/Instrument+Sans)
  (400, 500, 600) for everything you read in the app; JetBrains Mono (500, 600) for
  anything that names a value: form and field IDs, slugs, URLs, API keys and
  their prefixes, action parameters, webhook and MCP endpoints. Both load
  through `next/font` in `webapp/src/app/layout.tsx`, which downloads them at
  build time and serves them from the app. No page requests fonts.googleapis.com
  or fonts.gstatic.com — a privacy-friendly form builder doesn't tell Google who
  opened a form.
- **Respondent forms keep their typeface: Public Sans**, loaded the same way
  (self-hosted through `next/font`, all weights). It is the `font-form`
  utility, worn by the form renderers (`LayoutWrapper`, the trust strip) and
  by the respondent routes (`RespondentTypeface`, which also puts it on
  `<body>` so popovers and toasts that portal out of a form match). The builder
  canvas and previews reuse the renderers, so creators see the respondents'
  typeface. A published form's computed font family is the same as before.
- **The Leaflet serif.** The Leaflet form style (§9) adds one serif,
  [Source Serif 4](https://fonts.google.com/specimen/Source+Serif+4) at 600,
  for section numerals, section titles, question numbers and the ending's
  "What happens next" heading only; everything a respondent reads stays in
  Public Sans. It loads through `next/font` like the others
  (`webapp/src/assets/fonts/leaflet-serif.ts`, fallback Georgia), with
  `preload: false`, so only a page that draws a Leaflet glyph fetches it.
- **Utilities.** `font-sans` (the default), `font-mono` and `font-form`.
  `<code>`, `<kbd>`, `<pre>` and `<samp>` use the mono face automatically.
- **Body.** 1rem on a 1.55 line, set on `<body>`. Paragraphs inherit, so a
  container's own size wins (the builder's 24px question titles are TipTap
  paragraphs). Running text that should read as body copy takes `text-body`.
- **Page titles.** Weight 600, tighter as they get larger: `tracking-title-sm`
  (−0.018em, ~20px), `tracking-title` (−0.022em, ~24px), `tracking-title-lg`
  (−0.028em, 36px and up). The `.h1`–`.h5`, `.h2-new`, `.h3-new` and `.sh1`
  classes carry them.
- **Questions.** The builder canvas keeps its 24px question titles. Respondent
  question labels take their size from the form's style (§9: 16–18px Classic,
  17–18px Sheet, 19–21px Studio, 18px Leaflet), weight carrying the hierarchy
  rather than size. Answers wear the theme's ink, never larger than the
  question.

## 3. Layout and surfaces

- The app sits on paper mist (`black-100`). Cards and panels are white with a
  1px hairline (`black-300`); sections inside a white panel are divided by
  `black-300` hairlines, not by shadows or tinted bands.
- A line that sits on paper mist itself — a divider, a tab bar's baseline, the
  sidebar or header edge, a table's outer edge, the trust strip's top edge —
  takes the strong hairline (`black-400`): `#EAECF0` on `#F5F7FB` is 1.1:1 and
  disappears. `black-200` is a fill, never a line.
- **Links** inside running text are underlined at rest (WCAG 1.4.1); colour
  alone doesn't mark them. Hover changes the colour. Standalone links (a list
  of next steps, navigation, tab bars) may go without the underline.
- Provenance first: a respondent sees who is asking and how much is left
  before anything else (the header of every form page).
- **No eyebrows and no wash inside the app.** Sireto's marketing pages open
  sections with a ▶ mono eyebrow and pages with a periwinkle wash
  (`#BFD0FF → #E6EEFF → #F5F8FF`). The webapp has no marketing pages, so
  neither appears here. Small uppercase group labels in navigation are labels,
  not eyebrows: grey, sans, no ▶.

## 4. Trust surfaces

The trust strip on every form, the privacy panel it opens, the builder's trust
settings and the responder portal are where bettercollected keeps its promise.
They state who collects the data, why, for how long, and the rights the
respondent keeps, in plain language and in the respondent's language (English
or Dutch). They are calm surfaces — white, hairlines, ink text — never a
warning or a danger zone. Requesting deletion of one's own response is a normal
action, styled as one.

## 5. Honest patterns

- Show which questions are optional; never hide it to coerce answers.
- Consent and identity sharing are opt-in: checkboxes start unchecked.
- Errors are specific and quiet, with no alarm colours or urgency. Inside the
  app: olive or danger text next to the field. Inside a respondent form: the
  message in the theme's ink beside a danger-red alert icon, and the field's
  edge in signal red (§9).
- No surprise upsells, countdowns or fake scarcity. Pricing says what it costs.
- Copy is plain: no "oops", no dead ends; every error page offers a way on.

## 6. Shape and depth

- **Radius.** 6px: `rounded`, `rounded-md` and `rounded-lg` are all 6px, used
  by cards, buttons, inputs, menus, popovers and dialogs. Images take
  `rounded-image` (8px). Checkboxes use 4px. Pills stay `rounded-full`.
  Respondent-form renderers pin their own pixel radii, so the app's radius
  never reshapes a published form: fields, choice rows and scale cells take
  the form style's input radius (Classic 6px, Sheet 4px, Studio 0, Leaflet
  4px); respondent buttons are 8px (4px in Leaflet); checkboxes 4px.
- **Shadows.** Surfaces are separated by 1px hairlines. There is one shadow,
  `shadow-large` (`0 8px 24px rgb(16 24 40 / 0.12)`), for layers that genuinely
  float above the page: popovers, menus, select lists, tooltips, toasts, sheets,
  dialogs, and the small floating action buttons over images in the builder.
  The old glows (`formCard`, `logoCard`, `input`, `powered-by`,
  `suggestion-price`, `overview`, `blue-hue`, …) and the drop shadows are
  removed; the stylesheet defines no other shadow token.

## 7. Focus

Every interactive element shows a **2px Sireto-blue outline, 3px off the
element** when it has keyboard focus (and text fields whenever they are
focused, as browsers match `:focus-visible` there). One rule in `tailwind.css`
draws it, with `!important` so a leftover `outline-hidden` cannot switch it
off. Menu items and listbox options are the exception: their focus is the
highlighted row. Inside a respondent form, the outline takes the theme's
action colour (`--focus-ring`, set by the layout wrapper). The old blue glow
around inputs is gone; a focused input also turns its border blue.

## 8. Buttons

- **Primary**: `action` face, white text; hover `action-hover`, pressed
  `action-pressed`.
- **Secondary**: `black-800` face, white text. **Tertiary**: white face, Sireto
  blue border and text. **v2Button**: white face, `black-400` border, ink text.
  **Danger**: `#C43D3D`. **Ghost** variants have no face.
- **The key edge.** Buttons with a face carry a 3px inset bottom edge in a
  darker tone of their own colour (`key-edge` utility, colour in `--key-edge`):
  `action-pressed` under the primary blue, `brand-700` under the tertiary
  outline, `black-400` under the white v2 button, near-black under the dark
  secondary. Pressing moves the face down 1px and removes the edge; a disabled
  button has none. Ghost buttons have no face and no edge.
- The shadcn `Button` carries all of this. Buttons painted in a respondent
  form's theme colour pass `flat` and have no edge: the theme's `secondary`
  face, white semibold 16px text, at least 48px tall, 8px corners (4px in
  Leaflet). In Leaflet the page's button lines up with the question text,
  past the number column (§9).
- Focus is the global outline (§7), not a per-variant ring.

## 9. Form themes

Form themes (`webapp/src/constants/theme.ts`) are the creator's choice. Two
presets are specified here. The **Default** preset follows this system:

| Role | Value | Use |
|---|---|---|
| `primary` | `#101828` | Question and answer text (ink) |
| `secondary` | `#1649E2` | Buttons and selections (6.8:1 with white text) |
| `tertiary` | `#818CA0` | Field borders and affordances (3.2:1 on the accent) |
| `accent` | `#F5F7FB` | Page ground (paper mist) |

The other presets (apart from Leaflet, below) keep their values. A form's theme colours are stored inline
on the form when it is saved, so forms that already use the old Default keep
their colours; only forms set to Default from now on (and forms with no stored
theme at all) get the new values.

The **Leaflet** preset is the other one this system specifies; it is made
for the Leaflet style, and picking it switches the form to that style:

| Role | Value | Use |
|---|---|---|
| `primary` | `#1A1A1A` | Ink: questions, answers, running text |
| `secondary` | `#0B3D91` | Deep navy: section bars, buttons, numerals, selections (the only accent) |
| `tertiary` | `#6B7A99` | Slate control edge (4.3:1 on white) |
| `accent` | `#FFFFFF` | White sheet |

### In every form

These hold in every theme and every style; the colours are the form's own.

- **Fields.** Borders rest on the theme's `tertiary`, step to its `primary`
  on hover and commit to its `secondary` on focus (with the focus outline in
  the theme's `secondary`, §7). Inputs are white; answers wear the theme's
  `primary`. Every preset keeps `tertiary` at 3:1 or more on its own
  `accent`, so the field edge passes WCAG 1.4.11. Text fields, date and
  dropdown triggers take the style's input radius; the triggers are at least
  48px tall.
- **Choice rows.** Multiple choice, checkboxes, yes/no and the dropdown list
  are one family (`views/atoms/choice.tsx`): each option is a row at least
  48px tall with a real control at its start — an empty ring or box at rest,
  a filled dot or a ticked box when chosen (20px, 2px edge in the theme's
  `tertiary`, the theme's `secondary` when chosen) — and the chosen label in
  semibold, so selection reads in shape and weight, not colour alone. At
  rest the row has a `tertiary` edge, `primary` on hover, `secondary` with a
  10% `secondary` tint when chosen; Studio fills the chosen row solid with
  white text. Single-answer lists are a WAI-ARIA radio group (one tab stop,
  arrow keys move and choose); multi-answer lists say "Choose as many as you
  like." above the options.
- **Scales and ratings.** Number scales are 48px square cells: white face,
  number in the theme's ink, `tertiary` edge, ink on hover; the chosen cell
  fills with `secondary`, white semibold number. Star ratings sit in 48px
  targets (40px stars), filled and outlined in `secondary`.
- **Progress.** A 4px bar across the top of every question page: `secondary`
  on a 20% `tertiary` track, square ends, easing 300ms (none under reduced
  motion). It is decorative; "Page x of y" in the header says the same in
  words. Back and the page count sit in the header row; Back is at least
  44px tall.
- **Required and optional.** Every answerable question is marked one way or
  the other: required with an asterisk (read out as "required"), optional
  with the word "Optional". The asterisk is danger red (`#C43D3D`) where that
  reaches 4.5:1 on the form's ground, else the theme's ink; in Leaflet it is
  signal red (`#C8102E`) on the same rule.
- **Validation.** The message sits under the field in the theme's ink, 15px
  medium, after a danger-red alert icon; the field's own controls carry
  `aria-invalid` and are described by the message. While it shows, the
  field's edge (inputs, triggers, choice controls) turns signal red
  (`#C8102E`) where that reaches the 3:1 a control boundary needs on the
  page, else the theme's ink.
- **Why we ask this.** A creator's reason for asking sits under the question
  at 14px, "Why we ask this" in semibold ink, against a 2px rule in the
  theme's `tertiary` (Leaflet: a 3px rule in its `secondary`), so it belongs
  to the form's palette, not the app's blue.
- **Secondary text.** Descriptions and introductions are set in the theme's
  own ink mixed a little towards the page (`softInk`), kept at 7:1 or more,
  rather than a fixed grey that would sit off-hue on tinted presets. Text in
  the action colour (links, numerals, the Leaflet header) uses `secondary`
  only where it reads at 4.5:1 on the page, else the ink (`actionInk`).
- **Welcome and ending.** One left edge or centred, as the page's layout
  says: the title in the theme's ink (bold, 32px, 40px from `sm`, at most
  22ch), the introduction in soft ink (17px, 60ch), then the notes and the
  button as one group. Default copy is plain and in the respondent's
  language: "Start", "Thank you", "Your answers have been sent."
- **Type and buttons.** Public Sans throughout (§2); respondent buttons are
  flat (§8).

### Styles

A theme's **style** (`styleTokens` in
`webapp/src/views/molecules/theme/theme-shared.tsx`) changes the register —
label type, input radius, how options and numbers are drawn — and never the
colours or the background. Classic is the default; Sheet, Studio and Leaflet
are opt-in.

| Style | Question label | Input radius | Options |
|---|---|---|---|
| Classic | 16px semibold (18px from `lg`) | 6px | Bordered rows |
| Sheet | Serif, 17px medium (18px from `lg`), ruled questions | 4px | Bordered rows |
| Studio | 19px bold, tight (21px from `lg`) | 0 | Bordered rows; chosen row solid |
| Leaflet | 18px semibold, 1.4 line | 4px | Ruled rows |

### Leaflet

A form that reads like a plain-language information leaflet: every page is a
numbered section, every question has a number, every reason is a margin note.
White sheet, one accent, no shadows, nothing decorative.

- **Section bar.** Each question page opens with a full-width bar in the
  theme's `secondary`, edge to edge, straight under the 56px header row (whose
  hairline is the Leaflet rule): the serif section numeral (28px) in the
  number column and the section title (serif 22px, 1.25 line) in white. The
  page is top-aligned rather than centred so the bar starts at the top.
- **Section numbers and titles.** The section number is the page's position
  in the form, the same number "Page x of y" shows; a page skipped by logic
  skips its number too. The title is the page's opening heading; without
  one, the page is named after its first visible question; a page with no
  questions is "Section n" ("Deel n" in Dutch). Long fallback titles are
  shortened at a word boundary to 60 characters with an ellipsis, and the
  full title is what assistive tech reads.
- **Intro band.** When a page opens with a text block, its heading goes to
  the bar and the rest sits in a pale band under it (16px, 1.6 line): a tint
  of `secondary` over the page, kept light enough that the ink reads at 7:1
  or more on it.
- **Question numbers.** Questions are numbered n.1, n.2… among the questions
  the respondent can see right now (a question hidden by logic takes no
  number, so the sequence never has gaps). Text blocks, images and videos
  carry no number; a repeating group is one question. The number (serif 16px,
  tabular figures, in `secondary` where it reads at 4.5:1, else ink) sits in
  a margin column 34px wide, 44px when any number on the page needs four
  characters ("2.10", "10.1"), so every question on the page keeps one left
  edge. On centred full-width pages at least 880px wide, numbers hang outside
  the text measure. The number is hidden from assistive tech; the question
  is the group's name.
- **Ruled options.** No boxes: options sit on 1px rules (the `tertiary` mixed
  40% into the page — a separator, not a control edge; the radio and
  checkbox keep the full-strength `tertiary`), with a 5% `secondary` wash on
  hover.
- **Margin notes.** "Why we ask this" sits against a 3px `secondary` rule in
  soft ink.
- **Cover.** The welcome page repeats the 56px top rule, puts the form's
  title on the bar as the page heading (serif, 30px, 38px from `sm`, at most
  24ch), the introduction in the band, then "In this form": a numbered
  contents list of every page with the same title its bar shows, on rules.
- **Ending.** The title on the bar, the message in the band, then "What
  happens next" (serif 22px) with labelled rows on rules — how long the
  answers are kept and the respondent's rights, each term in semibold
  followed by a colon — and the submission receipt.
- **Privacy panel.** In Leaflet the trust strip's panel sets its terms like
  the margin notes, bold sentence case with a colon ("How long they are
  kept:"), not small uppercase labels, and marks the chosen language in the
  theme's `secondary`. The retention period is worded the same in the panel
  and on the ending.
- **Buttons.** Navy (`secondary`), 4px corners, left-aligned with the
  question text.
- **No borrowed look.** Leaflet's navy bar, serif numerals and ruled
  sections are its own and claim no one else's identity: keep its own hue
  (`#0B3D91`), never add a vertical ribbon, emblem, crest or seal motif, and
  keep "Powered by bettercollected" visible on every Leaflet page (it goes
  only when the creator turns branding off, as in every style). The rule is
  about what *we* add: an organisation's own uploaded logo is shown as it
  was provided (see "Organisation logo" below).

### Organisation logo

A creator can show their organisation's logo at the top of every page of a
form, in every style (`views/molecules/form/form-logo-strip.tsx`; rules in
`utils/form-logo.ts` and the backend's `services/form_logo.py`).

- **The strip.** A calm band at the very top of every page — welcome,
  question pages, ending — above the page header. Classic, Sheet and Studio:
  the theme's page colour (`accent`) with a 1px rule under it (the
  `tertiary` mixed 40% into the page, like the Leaflet rule). Leaflet: a
  white band with no rule of its own, above the 56px top row of question
  pages (Back and the page count), whose rule closes the masthead, and the
  section bar. On the welcome and ending pages the account control moves
  into the strip's row, on the column's right edge and centred on the logo,
  so the row that held it goes (in Leaflet the section bar follows the strip
  directly); without a logo nothing changes. The strip's height is fixed
  (64px, 72px from `sm`; on the welcome page 80px, 96px from `sm`), so
  nothing moves when the image arrives. The strip holds the logo and nothing
  else: no bar, ribbon or motif of ours.
- **Size.** At most 40px tall on phones and 48px from `sm` on question and
  ending pages, 56px and 64px on the welcome page; at most 200px wide (260px
  from `sm`; 240px and 320px on the welcome page). Proportions kept
  (`object-fit: contain`), never drawn larger than the file itself.
- **Position.** Left (the default) on the form column's left edge, or
  centred on the column (keeping the account control's width free on both
  sides, so it stays centred and never runs under the control; a wide logo
  shrinks within its room). It follows the page's column: left-aligned pages,
  and the content half of the image layouts.
- **Alt text.** The creator's alt text, else the workspace's name. A logo
  that spells the organisation's name still names it once: the alt text is
  the image's words, not decoration.
- **Workspace logo.** With "Use workspace logo when the form has none"
  (off by default), a form without a logo of its own shows the workspace's
  profile image.
- **Files.** PNG, JPEG or WebP only, recognised by their first bytes and
  decoded once; at most 1 MB and 16–3000px on each side; never SVG. Stored
  in our own storage and served from there, so a respondent page makes no
  third-party request for it; a logo URL sent in a form body is ignored. A
  copy of a form, or a form made from a template, gets its own copy of the
  file. Replacing or removing the logo changes the draft; the file the live
  form shows is deleted once a publish no longer uses it, and a deleted
  form's logo files go with it.
- **Start stays in view.** The strip counts against the room the welcome
  page has, so the privacy panel still opens by default only when Start
  stays in view with it open (`utils/panel-fit.ts`).
- **Builder.** Design tab, "Organisation logo": upload with a preview,
  Replace and Remove, Left or Centre, alt text, and the workspace-logo
  switch. The canvas shows the strip as respondents will see it.

## 10. Brand

- **Name and wordmark.** bettercollected keeps its name and wordmark, in Sireto
  blue and ink (`components/icons/bettercollected-logo.tsx`,
  `…-small-logo.tsx`, `components/ui/logo.tsx`, favicon and app icons).
- **Footer.** Public and auth pages (sign-in, not-found, error, the responder
  portal) end with one quiet line:
  "A product of Sireto B.V. · Sireto® is a registered trademark of Sireto B.V.",
  where "A product of Sireto B.V." links to https://sireto.com
  (`components/layout/sireto-footer.tsx`, translated in English and Dutch). On a
  workspace's custom domain the portal shows neither this line nor the
  "Powered by" caption. Respondent forms carry the trust strip instead.
- **Emails** (`auth/auth/app/templates`, `temporal/actions-executor/templates`):
  the same palette, Instrument Sans with system fallbacks, the wordmark, and
  the Sireto line in the footer.
- **"Powered by bettercollected".** A quiet caption in `black-600`, or a white
  badge with a hairline edge. No glow.

## 11. Not brought over from sireto.com

- The illustrations, their motion, the charcoal band and the film grain: they
  tell Sireto's own story.
- Sireto's coded accents, magenta and purple: they mean NormLogic and its
  engine.
- The ▶ eyebrows and the periwinkle hero wash (§3), since the webapp has no
  marketing pages.

## 12. Browser support

Tailwind CSS 4 output relies on cascade layers, `@property`, `color-mix()` and
native nesting, so the styled interface needs **Safari 16.4+, Chrome 111+ or
Firefox 128+**. Older browsers — including respondents on older phones — get
unstyled pages. Keep this in mind before relying on newer CSS features in
respondent-facing code.

## 13. Contrast reference

WCAG 2.1 AA: 4.5:1 for text (3:1 at 24px, or 18.66px bold, and up), 3:1 for
control boundaries and meaningful icons.

| Pair | Ratio |
|---|---|
| Ink `#101828` on paper mist `#F5F7FB` | 16.6:1 |
| Body `#5A6478` on paper mist | 5.6:1 |
| Captions `#667085` on paper mist / white | 4.6:1 / 5.0:1 |
| Sireto blue `#123FC9` on paper mist | 7.6:1 |
| White on primary face `#1649E2` | 6.8:1 |
| Olive `#8A6800` on yellow tint `#FFF7DB` | 4.8:1 |
| Success text `#027A48` on white | 5.4:1 |
| Control edge `#818CA0` on paper mist / white | 3.2:1 / 3.4:1 |
| Leaflet ink `#1A1A1A` on white / on its intro band `#E9EEF5` | 17.4:1 / 14.9:1 |
| White on Leaflet navy `#0B3D91` (and navy on white) | 10.0:1 |
| Leaflet control edge `#6B7A99` on white | 4.3:1 |
| Signal red `#C8102E` on white / paper mist | 5.9:1 / 5.5:1 |
| Leaflet rule `#C4CAD6` on white (separator only, not a control edge) | 1.6:1 |
