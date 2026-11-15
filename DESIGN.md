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

One blue ramp (`brand-*`) and one neutral ramp (`black-*`), and on top of them
a small set of role tokens (Daybreak, below) for the app's own ground, text,
accents, status and charts. Blue is the only action colour in Daybreak and in
every respondent form (a workspace that chooses the Pigment theme gets iris
instead, inside the app only; see "Pigment theme"). Nothing else carries
product meaning; status colours (success, warning, danger) appear only where
they say something, and every colour that means something also has a word, an
icon, a dot, a heavier weight or a shape beside it.

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
| `black-100` | `#F5F7FB` | Paper mist: the ground respondent routes keep (the app itself sits on `canvas`, below) |
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

No pink, no gradients, and no orange except the single coral accent below.
Both rules hold for Daybreak and for respondent forms; the Pigment theme (below) is
the one place they are set aside, for the creator app of a workspace that chose it.
The old bright blue (`#0764EB`), the old trust blue (`#2456CC`) and the
duplicate `new-*` ramps are gone.

### Daybreak: the app's role tokens

The ramps above keep their values, because respondent forms, the trust strip
and the "Powered by" badge read them directly. The app's own surfaces take the
roles below. They are not plain `@theme` values: each is a variable of an **app
theme scope** (`--app-canvas`, `--app-ink`, …, and `--series-1…6` for charts),
and the Tailwind utilities (`bg-canvas`, `text-ink`, `bg-ok-tint`, `fill-series-1`)
read those variables through an `@theme inline` block. The default theme is
`[data-app-theme='daybreak']`. Light only: the app has no dark theme.

| Token | Value | Role |
|---|---|---|
| `canvas` | `#F3F6FF` | App ground: the `body`, the builder's mat, the Report page |
| `surface` | `#FFFFFF` | Cards, panels, dialogs. Cards stay white |
| `sunken` | `#E8EDFF` | Wells, table heads, chart tracks, quiet pills, hover |
| `hairline` | `#DCE2F5` | Separator on a surface |
| `hairline-strong` | `#BDC8E8` | Separator or card edge on the canvas (decorative, not a control edge) |
| `control-edge` | `#6E7CA8` | Edge of a control (4.1:1 on white). The older `control` stays at `#818CA0` |
| `ink` | `#0E1737` | Headings and answers |
| `copy` | `#3C4872` | Running text |
| `ink-muted` | `#56628C` | Labels and captions |
| `brand-tint` | alias of `brand-100` | Selected row, active navigation |
| `link` | alias of `brand-600` | Links, and blue text on a tint |
| `sun`, `sun-tint`, `sun-ink` | `#FFB400`, `#FFF1C7`, `#6B4700` | The sun accent: a moment, a highlight, a "why we ask" rule. Fill only; text uses `sun-ink` on the tint |
| `coral`, `coral-tint`, `coral-ink` | `#FF6A48`, `#FFE4DC`, `#A22F14` | The one coral accent: something is waiting for you. Fill only; text uses `coral-ink` on the tint |
| `ok`, `warn`, `bad`, `info` | `#0A6F45`, `#7A4B00`, `#B42B2B`, `#1035A8` | Status text. Each has a `-fill` for icons and a `-tint` for backgrounds |
| `series-1` … `series-6` | `#2A55E0`, `#158591`, `#12471D`, `#6C2FBC`, `#BB7A0A`, `#5B6888` | Report series: blue, teal, deep green, violet, ochre, slate. Light and dark steps alternate, no red, and none is near `bad` |

The names `muted` and `accent` are left alone on purpose: shadcn components
already use those utility names, and defining them would paint those
components.

**Where colour goes.**

- **Wayfinding.** The active navigation item is the blue tint with blue
  (`link`) text; inactive items are `copy` on the ground, their icons
  `ink-muted`. No colour per navigation group.
- **Surfaces.** The canvas is `canvas`, cards are white. No tinted table rows,
  coloured card headers or gradients.
- **Selection.** A chosen option or row is the blue tint with a 2px blue edge
  (the `option-selected` utility: the 1px border plus a 1px inset line, so
  nothing shifts) and always a check, a dot or a heavier label with it.
- **Status.** A status is a dot and a word in a tinted pill (`StatusPill`):
  ok, warn, bad, info or neutral. The dot takes the text colour. A pill never
  stands for a state by colour alone, and red appears only where something is
  wrong.
- **"Why we ask this"** in the creator's own settings carries a 2px sun rule.
  It is the second cue; the words carry the meaning. Inside a form the rule
  stays the form theme's (§9).
- **Charts.** One blue (`series-1`) for single-question bars and lines; the six
  series for donuts and multi-series, each at least 3:1 on the white card, with
  a value written beside every mark and a pattern on every donut slice after
  the first, so colour is never the only code. The series also hold when seen
  with deuteranopia or protanopia: neighbouring series (and the next but one)
  differ in lightness and in simulated colour, and none is near the danger red
  (`daybreak-tokens.test.ts` states the thresholds and measures them). The tracks behind bars are
  `sunken`.

- **Moments.** One tinted band tops the forms dashboard: the person's first name
  and the time of day, one sentence about where things stand and one next step
  (the requests waiting, a draft to finish), with the sun and hills motif (`DaybreakArt`, inline SVG, the action blue and the sun accent).
  A step a member's role cannot take (reviewing requests, finishing a draft, creating a form) is
  not offered, and a Viewer gets a neutral line and no button. With no forms the
  band only greets: the empty state below carries the one sentence and the one
  action, so the screen never has two buttons doing the same thing. The same motif sits, still, in a tinted panel on the empty states. No other
  surface carries it: never inside the builder canvas, a table or a respondent form.
- **Empty states** are one component (`EmptyState`): a white card on the canvas
  with the motif in a tinted panel, a title, one plain sentence and at most one
  primary action (blue), offered only when the member may take it and, for
  "Share the form", only for a form that is published, open and not hidden. A
  search or a filter with no match leaves the picture out and offers a way back
  ("Clear search", which puts focus back in the search box, and "Clear filters"). Copy is calm: it
  says nothing is wrong and what to do, with no exclamation marks.
- **Forms tell apart.** Each form has a tile in lists and headers: its initial
  in a tint with its ink, from a pair picked by the form's id (`formHueIndex`,
  FNV-1a over the trimmed, lower-cased id, modulo five; `FormAvatar`). The pairs
  are scope variables `--form-hue-0-bg/-ink` to `--form-hue-4-bg/-ink` (teal,
  sun, sand, blue and violet tints, each pair at least 4.5:1), so a later
  theme supplies its own five. No tile is a signal colour: coral means "waiting
  for you" and green, amber and red are status, so none of them is a form's colour. The tile is decoration beside the title; the
  responder portal does not show it.
- **Something is waiting for you.** A coral count badge (`CountBadge`: the
  number on coral tint in coral ink, with the whole phrase as its accessible
  name) marks a navigation item that needs the person, today deletion requests
  with a pending count. It is a number, never a bare dot, and it never pulses or
  turns red: it informs and does not press.
- **Card edges on the canvas.** A card that sits directly on the canvas (the form
  rows, the report cards, the settings cards) takes the strong hairline
  (`border-hairline-strong`) on a `surface` ground; inside a white panel the
  plain hairline is enough.

**Where colour does not go.** The primary button is always `action` blue: sun
and coral never colour a button, a link or a form control. Colour never carries
urgency or pressure (§5). Neither accent is used for body text, and neither
appears inside a respondent form, whose colours are the form's own theme (§9).
Coral is the single exception to "no orange", and it is kept to one role.

**What reads the semantic roles, and what still reads the ramps.** The ramps
(`brand-*` and `black-*`) are not renamed and stay frozen. The creator app's
chrome reads roles instead of the ramp steps it used to: the app ground and the
builder mat, active navigation, the selected option or row, status pills, the
"why we ask" note and the report series, tracks and grid, and also the **chrome
roles**: `app-primary` (blue icons, borders, text actions and rings),
`app-primary-deep` (text links), `app-primary-soft`, `app-primary-tint`,
`app-edge` and `app-edge-strong` (card, table and row edges), `app-wash` and
`app-wash-strong` (hover and quiet fills, tabs, tracks) and `app-control` (the
edge of a control). In Daybreak each is the ramp step it replaced, so the app
did not change; in another theme each is that theme's value. Every utility
falls back to the ramp step where no theme scope is around.

What still reads the ramps: text steps (`text-black-600/700/800/900`, the
neutral greys of body text), `bg-white` surfaces, the flow view's node
illustrations, the older status and AI chips that carry a literal hex, anything
a form theme paints, and every file that draws a respondent's form or page
(the form renderers and their field components, the theme gallery and its
previews, the trust strip and the "Powered by" badge, the respondent sign-in
and the responder portal): they keep the frozen values, which is also why a
form previewed inside the builder looks the same in every app theme.

**Respondent routes keep paper mist.** `data-app-theme` is set by the creator
app's layouts only: the admin portal (dashboard, builder, settings, the Report
page, the workspace picker) and the creator's sign-in. The respondent's
sign-in (`/login?type=responder`, also served on custom domains) is a respondent
route and does not carry it. The variables are also defined on `<html>`, in a
rule of its own (`html:has([data-app-theme='daybreak'])`; a browser without
`:has` drops only that rule), while the document holds a scoped element, so
menus, dialogs and toasts that portal out of the app read them too. A page
without the attribute (the form on the form domain and on a custom domain, the
responder portal, the respondent's sign-in) has none of the
variables: its `<html>` and `<body>` ground falls back to `black-100`, paper mist,
from the server-rendered markup. `views/molecules/theme/respondent-colours-pin.test.tsx`
pins the Default preset's resolved colours and the hex values the trust strip
and the "Powered by" badge resolve to, and `assets/css/daybreak-tokens.test.ts`
checks the token values, the scope, which layouts carry the attribute, and every
contrast pair listed here.

**How a second app theme plugs in.** Add another block of the same shape,
`[data-app-theme='<name>']` plus its `html:has(...)` mirror in a second rule, that sets the
same `--app-*` and `--series-*` variables, and set the attribute on the app
layouts (it can follow a workspace setting). Components do not change: they use
the semantic utilities, never a hex or a ramp step, for app chrome. The ramps and
the respondent routes do not change either.

### Pigment theme

Pigment is the second app theme, **a workspace's own choice** (owners and admins,
Themes page, "Appearance"; `docs/app-theme.md`). It is a block of the shape above,
`[data-app-theme='pigment']` with its own `html:has(...)` rule after Daybreak's, so
inside a Pigment workspace the same utilities resolve to other values. It exists
only in the creator app, only in light, and only on an instance whose operator has
switched it on. Respondent forms never wear it: they carry no theme attribute, and
`respondent-colours-pin.test.tsx` holds their colours.

| Role | Daybreak | Pigment |
|---|---|---|
| Ground (`canvas`) | `#F3F6FF` periwinkle air | `#FBF7F1` cream paper |
| Card (`surface`) | `#FFFFFF` | `#FFFFFF` |
| Wells, table heads (`sunken`) | `#E8EDFF` | `#F2EBDF` |
| Separators (`hairline`, `hairline-strong`) | `#DCE2F5`, `#BDC8E8` | `#E9E1D4`, `#CFC4B1` |
| Control edge (`control-edge`) | `#6E7CA8` | `#7C7396` |
| Text (`ink`, `copy`, `ink-muted`) | `#0E1737`, `#3C4872`, `#56628C` | `#1A1238`, `#443C66`, `#5F577F` |
| Action (`app-action`, hover, pressed) | `#1649E2`, `#123FC9`, `#0E2D8F` | iris `#4B35DB`, `#3E29C4`, `#2F1DA2` |
| Focus ring (`app-focus-ring`) | `#123FC9` | iris `#4B35DB` |
| Selected, active nav (`brand-tint`), link | `#E0E8FF`, `#1035A8` | `#E8E4FF`, `#3E29C4` |
| Accent (`app-accent`, tint, ink) | sun `#FFB400`, `#FFF1C7`, `#6B4700` | sun `#FFC62E`, `#FFF0C2`, `#664600` |
| Attention (`app-attention`, tint, ink) | coral `#FF6A48`, `#FFE4DC`, `#A22F14` | coral `#FF7A61`, `#FFE2DC`, `#A3301A` |
| Status (`ok`, `warn`, `bad`, `info`) | as in the table above | `#0B6B4A`, `#7A4B00`, `#B0302A`, `#1B5FA8` (each with fill and tint) |
| Chart series 1 to 6 | blue, teal, deep green, violet, ochre, slate | iris, deep green, ochre, orchid, warm dark neutral, teal (no red; see below) |

**The series.** Pigment's six chart series are chosen to be told apart without
colour: neighbours differ in lightness and not only in hue (the relative
luminance of series *i* and *i+1* is at least 1.3 times apart, and of *i* and
*i+2* at least 1.5), they stay at least 40 apart (CIE76 ΔE) when simulated for
deuteranopia and protanopia, each is at least 3:1 on a white card and on a
track, and none is a red: every series keeps a hue and lightness distance from
`bad` (ΔE of at least 40), so no answer reads as a warning. Red and green are
never neighbours.

**The chrome roles.** The primary button, the edge of a chosen option and the
keyboard focus ring of the creator app read `app-action`, `app-on-action` and
`app-focus-ring` (utilities `bg-app-action`, `hover:bg-app-action-hover`,
`text-app-on-action`), and what used to be called sun and coral is also available
as `app-accent*` and `app-attention*` (`sun` and `coral` stay as aliases, so
nothing was renamed). In Daybreak each role is the value it always had. Where no
theme scope is around, as on a respondent route, the action utilities fall back to
the frozen `action` and `brand-500`, so a respondent page looks exactly as before.

**The pigments.** Tomato `#FF8A73`, sun `#FFC62E`, mint `#5FD9B0`, sky `#6BBEF7`
and orchid `#D9A0FF` are flat fills, set in the Pigment scope as `--app-pig-*`.
They give each form its identity colour: the form's tile takes the pigment of its
hue index (`lib/form-hue.ts`) with the one ink `#1A1238` on it (7.7 to 11.3:1).
Their dosage rules:

- **Never text.** There is no pigment text utility. A pigment is a fill that
  carries ink, never the colour of a word, an icon or a focus ring: none of the
  five reaches 3:1 on white (1.6 to 2.3:1), and a test states it.
- **At most five pigments plus iris on one screen**, and at most one row of loud
  tiles.
- **Never a primary button.** Iris is the action colour; a pigment never is.
- **Tomato never means error.** Danger is `bad`, a deeper red (`#B0302A`), always
  with an icon and words. Tomato is identity only.
- **Always with the form's name beside it.** A tile is the second cue, never the
  only one.

**What still reads the ramps.** The creator app's blue and neutral chrome reads
the roles above, so a Pigment workspace is iris and warm paper throughout the
dashboard, the builder, the responses, the report and the settings: links and
text actions, avatars, switches, checkboxes and radios (native controls take
the iris through `accent-color`), tabs, edges, washes and the pills. What stays
as it is: the neutral text steps (`text-black-*`), anything a form theme paints
(so a form inside the builder keeps its own colours), and the respondent routes.

**Charts in a Pigment workspace.** On the report's bar and donut cards of a
choice question, each answer keeps its own colour on every card: the series
(`series-1` to `series-5`, never a raw pigment) of the answer's position among
the question's options, so "North" is the same colour in a bar card, a donut card
and a filtered report. The sixth option and later, "Other", a removed option and
"no answer" share the neutral (`--app-viz-neutral`, 4.4:1 on white). Yes/no and
rating questions, lines, tiles and tables keep one colour. Position carries the
identity and colour is the second cue: the answers are listed in the question's
option order, which is the order of the colours, and every value is printed
beside its mark. The series are chosen so that neighbours differ in lightness and
stay apart for deuteranopia and protanopia, and none is a red (see "The
series"). A donut keeps its patterns by position, and the table and the CSV are
unchanged. In
Daybreak a single-question bar stays one blue and a donut takes the series in
turn.

**The nav chips.** In a Pigment scope each group of the dashboard menu has a small
pigment chip before its label (tomato, sky, mint). It is a `::before` of the
label, drawn only inside a Pigment scope: Daybreak gets no element and no pixel.
It is decorative and carries no text.

**A form is never in the app's colours.** The builder canvas, the preview page and
the preview dialog sit inside the scope of a workspace, but they show the form as a
respondent sees it. The root of the form (`LayoutWrapper`, `formRootProps`) therefore
sets every app role that a form component reads with a frozen fallback
(`--app-action`, its hover and pressed steps, `--app-on-action`, `--app-focus-ring`;
the list is `APP_ROLES_RESET_ON_FORMS` in `lib/app-theme.ts`) to `initial`, so the
button and the focus ring are the form's own or the frozen blue, in Pigment too. Outside
a scope (the real respondent page) nothing is set.

`assets/css/app-theme.test.ts` holds the two blocks: Pigment sets every variable
Daybreak sets (and the pigments); every text and control pair of both themes passes
WCAG from the values in the CSS; no theme block declares a ramp; and the previews
on the Appearance card are the colours of the blocks.

## 2. Type

- **Faces.** [Instrument Sans](https://fonts.google.com/specimen/Instrument+Sans)
  (400, 500, 600) for everything you read in the app; JetBrains Mono (500, 600) for
  anything that names a value: form and field IDs, slugs, URLs, API keys and
  their prefixes, action parameters, webhook and MCP endpoints. Both load
  through `next/font/local` in `webapp/src/app/layout.tsx`, from the woff2
  files of the `@fontsource` npm packages (OFL-1.1, latin subset), and are
  served from the app. Neither the build nor any page requests
  fonts.googleapis.com or fonts.gstatic.com — a privacy-friendly form builder
  doesn't tell Google who opened a form, and a build doesn't fail when Google
  can't be reached. Don't use `next/font/google`.
- **Respondent forms keep their typeface: Public Sans**, loaded the same way
  (self-hosted through `next/font/local`, all weights via the variable font). It is the `font-form`
  utility, worn by the form renderers (`LayoutWrapper`, the trust strip) and
  by the respondent routes (`RespondentTypeface`, which also puts it on
  `<body>` so popovers and toasts that portal out of a form match). The builder
  canvas and previews reuse the renderers, so creators see the respondents'
  typeface. A published form's computed font family is the same as before.
- **The Leaflet serif.** The Leaflet form style (§9) adds one serif,
  [Source Serif 4](https://fonts.google.com/specimen/Source+Serif+4) at 600,
  for section numerals, section titles, question numbers and the ending's
  "What happens next" heading only; everything a respondent reads stays in
  Public Sans. It loads through `next/font/local` like the others
  (`webapp/src/assets/fonts/leaflet-serif.ts`, fallback Georgia), with
  `preload: false`, so only a page that draws a Leaflet glyph fetches it.
- **Theme faces.** A form theme may pick its title, text and data faces
  (§9): Atkinson Hyperlegible Next, Archivo (with its width axis), Besley
  (with italic), Rubik and Atkinson Hyperlegible Mono, besides Public Sans.
  Each is one variable latin file from its `@fontsource-variable` package
  (OFL-1.1, `webapp/THIRD_PARTY_NOTICES.md`), loaded through
  `next/font/local` (`webapp/src/assets/fonts/theme-faces.ts`) with
  `preload: false`: a respondent page fetches only the faces its theme draws,
  and a form without them fetches none.
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

- The app sits on the canvas (`canvas`; respondent routes keep paper mist, §1). Cards and panels are white with a
  1px hairline (`black-300`); sections inside a white panel are divided by
  `black-300` hairlines, not by shadows or tinted bands.
- A line that sits on the canvas or paper mist itself — a divider, a tab bar's baseline, the
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
  not eyebrows: grey, sans, no ▶. The canvas (§1) is a flat ground, not that wash.

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
action colour (`--focus-ring`, set by the layout wrapper); inside an app theme
scope it is the theme's `--app-focus-ring` (Sireto blue in Daybreak, iris in
Pigment). The old blue glow
around inputs is gone; a focused input also turns its border blue.

## 8. Buttons

- **Primary**: `action` face, white text; hover `action-hover`, pressed
  `action-pressed`. In the creator app the face is the theme's `app-action`
  (the same blue in Daybreak, iris in Pigment).
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

**New forms start with Leaflet.** A form that brings no theme of its own
starts with the Leaflet preset, and so the Leaflet style: a blank form, a
form made with the AI assistant (unless the request asks for other colours),
through the API or MCP, a PDF import without brand colours, a Google Forms or
Typeform import. A form made from a template keeps the template's theme and a
copy keeps its source's. Stored forms never change, and a form with no stored
theme still renders as Default. Default stays in the picker. One constant
names the preset on each side (`NEW_FORM_THEME_TITLE` in
`webapp/src/constants/theme.ts`, `NEW_FORM_THEME` in
`backend/app/constants/themes.py`), and a test keeps them together.

**One list of presets.** The webapp's list (`ThemeColors`) is the source of
truth: names, colours and styles. The backend keeps a copy for the forms it
dresses (the AI assistant, the API, MCP, imports), and a backend test fails
when the two drift, so a preset the AI picks shows as that preset in the
builder's picker (which finds it by title). The backend's older names (Blue,
Green, Red, Black, Orange, Purple) still work and mean the nearest preset
(Ocean, Forest, Cherry, Mono, Sunset, Lavender).

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
- **Lettered option cards.** A theme that sets its own corners (`radius`,
  below; the complete looks do) letters its answer options: a 28px key
  letter in the data face stands where the ring or box was (A, B, C…; Yes
  and No take their own initials, Y and N, J and N in Dutch), outlined in
  the `tertiary` with the letter in ink at rest, filled with the chosen
  colour once chosen, and a chosen card ends in a check mark, so the choice
  shows in colour, a mark and weight. While an option has focus, pressing
  its letter (no modifier keys) chooses it, or ticks and unticks it, and
  moves focus there; the letters work only inside the focused list, never
  in a text field (WCAG 2.1.4), and each option names its key in
  `aria-keyshortcuts`, the letter itself being hidden from assistive tech.
  The check mark grows in over 160ms, and simply appears under reduced
  motion. A theme without corners of its own keeps the ring and box, so
  stored forms don't change. The dropdown's list is never lettered.
- **Scales and ratings.** Number scales are 48px square cells: white face,
  number in the theme's ink, `tertiary` edge, ink on hover; the chosen cell
  fills with `secondary`, white semibold number, and wears a small check
  mark in its corner. Star ratings sit in 48px targets (40px stars), filled
  and outlined in `secondary`, and say the answer in words under the stars
  with a check mark ("4 of 5"). Both are radio groups named by their
  question (`views/atoms/scale-radio-group.tsx`): one tab stop, the arrow
  keys, Home and End choose, and so does a digit key (named in
  `aria-keyshortcuts`) while focus is in the group. A key press does not move
  on to the next question; a click does, after 200ms, as before. The mark
  that appears on choosing (the dot or tick of an option, the check, the
  chosen star) grows in over 160-200ms when the respondent chooses it (not
  when a stored answer is shown again), and simply appears under reduced
  motion. The line under the stars is always there, empty until the first
  answer, so answering shifts nothing.
- **Progress.** A 4px bar across the top of every question page: `secondary`
  on a 20% `tertiary` track, square ends, easing 300ms (none under reduced
  motion). It is decorative; "Page x of y" in the header says the same in
  words, and the bar fills exactly that fraction (page 1 of 3 is a third; the
  welcome and ending pages are not steps; the ending fills it, and so does
  a page whose answers make it submit the form, where the header says "Last
  page"). Back and the page count sit in the header row; Back is at least
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
  flat (§8). A theme may set other faces and shapes (below).

### Type and shape

A theme may also set, each optional (`FormTheme` in
`webapp/src/constants/theme.ts`, the same lists in the backend):

| Key | Values | What it changes |
|---|---|---|
| `titleFont` | `public-sans`, `atkinson-next`, `archivo`, `besley`, `rubik`, `atkinson-mono` | Page titles (`h1`), question labels, a text block's headings |
| `bodyFont` | the same | Everything else respondents read, the trust strip and the page's popovers included |
| `dataFont` | the same | `font-mono` text, such as the submission number |
| `titleWidth` | `normal`, `expanded` | Page titles at 125% width, on a face with a width axis (Archivo) |
| `radius` | `sharp` (0), `soft` (6px), `round` (16px) | Fields, option cards and buttons |
| `buttonStyle` | `filled`, `outlined`, `pill` | Start, Continue, Submit and the ending's button |
| `highlight` | `#rrggbb` | The chosen answer, the "why we ask" and "optional" notes, the focus ring |
| `selection` | `#rrggbb` | The chosen answer alone (the highlight then keeps the notes and the focus ring) |

- **Absent means today.** A key left out (or null, as stored forms send it)
  sets nothing: a theme without these keys renders exactly as before, and so
  do all current presets. Picking a colour preset keeps the form's own type
  and shape, as it keeps its style; the highlight, a colour, comes from the
  preset. A title font left out follows the text (or the style's own title
  face, such as the Sheet serif).
- **One place.** The element that wears the theme (the page's
  `LayoutWrapper`, also the builder canvas and the previews) gets the keys
  as CSS variables and `data-form-*` attributes
  (`webapp/src/views/molecules/theme/theme-root.ts`); components read
  `var(--form-…, <their old value>)`, and the face rules in `tailwind.css`
  match only under their attribute.
- **Outlined buttons** are the page colour with a 2px edge and text in the
  secondary where it reads at 4.5:1 on the page, else the ink: text 4.5:1,
  edge 3:1. Pill buttons are filled and fully rounded.
- **The highlight** is held to the same rules where it is used: as an edge
  or the focus ring only at 3:1 on the page, as note text only at 4.5:1,
  else the ink takes its place. A light highlight (a lemon) fills the chosen
  option, with the ink on it and an ink edge; a dark one tints it, as the
  secondary does. The chosen state keeps its dot, tick and semibold text.
  A `selection` colour, held to the same rules, takes the chosen answer
  from the highlight: a rubric colour for the notes need not mark answers
  too (left out, the highlight, else the secondary, as before).

### Backgrounds and artwork

`background` dresses the page ground; `accent` stays the base colour.

- **Patterns** (`type: 'pattern'`): `dots`, `grid`, `stripes`, and
  - `columns`: a twelve-column hairline grid (four on phones) between the
    form gutter's margins, at 20% of the tertiary (about 1.3:1 on white).
    Decorative only; text keeps its contrast over it, and options at rest
    are filled with the page colour so no line runs through an answer.
  - `margin`: an exercise-book page. The page colour is the margin; a
    hairline rule in the highlight (else the tertiary) runs 56px left of the
    form column; right of it a white sheet carries the questions, where the
    ink reads at 4.5:1 on white (else the page colour). A left-aligned page
    and a page narrower than the column and its margin are all sheet.
- **Artwork** (`artwork: 'marble'`, with any ground): a marbled endpaper,
  first-party AVIF/WebP images bundled with the app
  (`webapp/src/assets/themes/marble/`, generated by `scripts/marble/`) with a
  blurred placeholder inlined, always decorative (`alt=""`), never under
  text. It fills the picture half of a welcome or ending page whose layout
  has one and no image of its own (a 120px band above the text on phones),
  with a striped headband in the highlight and the page colour at the spine.
  An ending without a picture half carries it as a band along the top.
- **The cover.** A welcome page set beside the artwork turns its text half
  into a cover: the secondary as the ground, the page colour as the ink, the
  button in the page colour with the secondary as its text. Only where the
  two read at 4.5:1 on each other, and not for a private form or the
  Leaflet style.
- **Display titles.** A theme with its own title face sets the welcome and
  ending titles as display type, sized by the page's width (2.5–5.5rem;
  1.75–6rem when expanded, so a long word fits a phone). Outlined buttons fill with their ink on hover.

### Complete looks

Two presets set the whole look at once: colours, every type and shape key
(normal width and filled buttons included, so nothing of the previous look
stays), the style, the background and the welcome layout they are made for.
Picking one (in the builder or with `set_theme_preset`) sets that layout on
a welcome page without an image of its own; picking a theme without
artwork afterwards returns a page left beside the artwork to the default.

| | Kantlijn | Raster |
|---|---|---|
| Colours | ink `#16261F`, cloth `#1E4D3B`, edge `#7D8C84`, blush `#F8EEEC` | ink `#0E0E14`, ultramarine `#2B2FD1`, edge `#6D7083`, white |
| Highlight, selection | rose `#A3305A` for notes, margin rule and focus; selection in the cloth | none: the ultramarine marks the respondent's own |
| Faces | Besley titles, Atkinson Hyperlegible Next text, Atkinson Hyperlegible Mono data | Archivo, expanded titles; Atkinson Hyperlegible Mono data |
| Shape | soft corners, filled buttons, Classic style | sharp corners, outlined buttons, Studio style |
| Background | `margin` pattern with the `marble` artwork | `columns` pattern |
| Welcome | beside the marble, as its cover | left aligned |
| Ending | the marble band | the submission number large in the data face (a Studio form with its own data face) |

### Styles

A theme's **style** (`styleTokens` in
`webapp/src/views/molecules/theme/theme-shared.tsx`) changes the register —
label type, input radius, how options and numbers are drawn — and never the
colours or the background. New forms start in Leaflet (with its preset,
above); a form with no style set is Classic; Sheet and Studio are opt-in.

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
  skips its number too. The title is, in this order: the page's own section
  title (a page setting, plain text, at most 120 characters); else the
  page's opening heading; else its first visible question; else "Section n"
  ("Deel n" in Dutch) for a page with no questions. The creator's own title
  and heading are shown in full; a fallback question title is shortened at a
  word boundary to 60 characters with an ellipsis, and the full title is
  what assistive tech reads. Whatever its source, the title is the bar's
  heading (h2, with the numeral).
- **Intro band.** When a page opens with a text block, its heading goes to
  the bar and the rest sits in a pale band under it (16px, 1.6 line): a tint
  of `secondary` over the page, kept light enough that the ink reads at 7:1
  or more on it. A page with a section title of its own keeps the whole
  block, heading included, in the band.
- **Editing the title.** In the builder the creator edits the title on the
  navy bar itself. With a section title set, or on a page without an opening
  heading, the bar holds a labelled one-line field ("Section title") whose
  placeholder is the title the bar falls back to, so it is clear what
  respondents see when it is left empty; clearing it returns to that
  fallback. A page that opens with a heading and has no section title edits
  that heading in place on the bar. The page's properties panel has the same
  "Section title" field (with the fallback as its placeholder), in every
  style. Other styles do not show it: they have no section bar, and a page
  heading would add a level they never had. The AI assistant (chat, review
  fixes) and the API/MCP `update_form` set or clear it with the
  `set_section_title` operation, and a generated multi-page form may come
  with short, plain section titles; neither is ever required.
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
  contents list of every page with the same title its bar shows (section
  title first), on rules.
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
- **Position.** Automatic by default: the logo follows the welcome page,
  centred on every page when the welcome page is centred, else on the left
  (a Leaflet welcome page reads from one left edge, so left). The creator's
  explicit Left (the form column's left edge) or Centre (centred on the
  column) always wins. Centred, the logo keeps the account control's width free on both
  sides, so it stays centred and never runs under the control; a wide logo
  shrinks within its room). It follows the page's column: left-aligned pages,
  and the content half of the image layouts.
- **Alt text.** The creator's alt text, else the workspace's name. A logo
  that spells the organisation's name still names it once: the alt text is
  the image's words, not decoration.
- **Workspace logo.** With "Use workspace logo when the form has none"
  (off by default), a form without a logo of its own shows the workspace's
  profile image.
- **Files.** PNG, JPEG or WebP only, recognised by their first bytes; at
  most 1 MB and 16–3000px on each side; never SVG. The API never decodes an
  upload: the isolated document sandbox decodes it, checks its size and
  re-encodes it (PNG stays PNG, JPEG and WebP at quality 90) without its
  metadata (EXIF and GPS, XMP, colour profiles, text), and only that
  re-encoding is stored, with its real content type. Without the sandbox
  the upload is refused, never decoded elsewhere. Stored
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
  Replace and Remove, Automatic (follows the welcome page), Left or Centre,
  alt text, and the workspace-logo
  switch. The canvas shows the strip as respondents will see it.

## 10. Brand

- **Name and wordmark.** The wordmark is the name itself, set the way the
  admin portal sets it: "bettercollected", lower case, Instrument Sans 600,
  −0.018em, in ink (`#101828`). No colour, no mark beside it, no trailing
  dot. It is drawn as outlines of that face
  (`components/icons/bettercollected-logo.tsx`, used through
  `components/ui/logo.tsx`), so it never waits for the font, and it is
  labelled "bettercollected" for assistive tech.
- **The mark.** Where the name doesn't fit, the wordmark's own "b" stands in,
  in ink (`…-small-logo.tsx`, `small-logo.tsx`). The favicon and app icons
  are that "b" on a white square with 22% corners. The email logo
  (`logo-200-20.png` on the public bucket) is the wordmark at 2×, shown at
  200 × 20.
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
| Ink `#0E1737` / copy `#3C4872` / ink-muted `#56628C` on the canvas `#F3F6FF` | 16.3:1 / 8.2:1 / 5.5:1 |
| Ink / copy / ink-muted on white | 17.5:1 / 8.9:1 / 6.0:1 |
| Ink-muted on `sunken` `#E8EDFF` (neutral pill) | 5.1:1 |
| Link `#1035A8` on white / on `brand-tint` `#E0E8FF` (active navigation) | 10.0:1 / 8.2:1 |
| Action `#1649E2` on white / canvas / `brand-tint` (selection edge) | 6.8:1 / 6.3:1 / 5.6:1 |
| Sireto blue `#123FC9` on white / canvas (the focus ring) | 8.1:1 / 7.5:1 |
| Control edge `#6E7CA8` on white / canvas | 4.1:1 / 3.8:1 |
| `sun-ink` on `sun-tint`; `coral-ink` on `coral-tint` | 7.4:1; 5.9:1 |
| `ok`, `warn`, `bad`, `info` text on their tints | 5.4:1, 6.6:1, 5.3:1, 8.2:1 |
| Series 1 to 6 as marks on white | 6.0, 4.4, 10.8, 7.6, 3.6, 5.6 (all at least 3:1; series 1 to 5 also at least 3:1 on the `sunken` bar track) |
