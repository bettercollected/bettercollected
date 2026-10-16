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
- **Utilities.** `font-sans` (the default), `font-mono` and `font-form`.
  `<code>`, `<kbd>`, `<pre>` and `<samp>` use the mono face automatically.
- **Body.** 1rem on a 1.55 line, set on `<body>`. Paragraphs inherit, so a
  container's own size wins (the builder's 24px question titles are TipTap
  paragraphs). Running text that should read as body copy takes `text-body`.
- **Page titles.** Weight 600, tighter as they get larger: `tracking-title-sm`
  (−0.018em, ~20px), `tracking-title` (−0.022em, ~24px), `tracking-title-lg`
  (−0.028em, 36px and up). The `.h1`–`.h5`, `.h2-new`, `.h3-new` and `.sh1`
  classes carry them.
- **Questions.** The builder and respondent forms keep the 24px question size.
  Answers wear the theme's ink, never larger than the question.

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
- Errors are specific and quiet (olive or danger text next to the field), with
  no alarm colours or urgency.
- No surprise upsells, countdowns or fake scarcity. Pricing says what it costs.
- Copy is plain: no "oops", no dead ends; every error page offers a way on.

## 6. Shape and depth

- **Radius.** 6px: `rounded`, `rounded-md` and `rounded-lg` are all 6px, used
  by cards, buttons, inputs, menus, popovers and dialogs. Images take
  `rounded-image` (8px). Checkboxes use 4px. Pills stay `rounded-full`.
  Respondent-form renderers pin their own pixel radii (`rounded-[4px]`,
  `rounded-[8px]`), so the app's radius never reshapes a published form.
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
  form's theme colour pass `flat` and have no edge (§9).
- Focus is the global outline (§7), not a per-variant ring.

## 9. Form themes

Form themes (`webapp/src/constants/theme.ts`) are the creator's choice. Only
the **Default** preset follows this system:

| Role | Value | Use |
|---|---|---|
| `primary` | `#101828` | Question and answer text (ink) |
| `secondary` | `#1649E2` | Buttons and selections (6.8:1 with white text) |
| `tertiary` | `#818CA0` | Field borders and affordances (3.2:1 on the accent) |
| `accent` | `#F5F7FB` | Page ground (paper mist) |

The other presets keep their values. A form's theme colours are stored inline
on the form when it is saved, so forms that already use the old Default keep
their colours; only forms set to Default from now on (and forms with no stored
theme at all) get the new values.

What changes inside forms, in every theme: field borders rest on the theme's
`tertiary`, step to its `primary` on hover and commit to its `secondary` on
focus (with the focus outline in the theme's `secondary`); the "Back" control
wears the theme's `primary`. The typeface (Public Sans), radii and button
shapes stay as they were. Every preset keeps
`tertiary` at 3:1 or more on its own `accent`, so the field edge passes WCAG
1.4.11 in every theme. Respondent buttons are flat (no key edge).

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
