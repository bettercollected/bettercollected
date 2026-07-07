# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
See [RELEASING.md](RELEASING.md) for how releases are cut.

> This file was introduced partway through the project's life, so history before
> `2.2.0` is captured by git tags and release notes rather than here.

## [Unreleased]

### Added

- **Answer piping / recall**: question titles can reference earlier answers or
  hidden fields ("Thanks, @name!") via an "@ Answer" menu in the builder's
  title toolbar — stored as inline TipTap nodes, resolved live in the
  responder runtime through the same value extractor conditional logic uses.
  Plain-text surfaces (field descriptions, thank-you message) support
  `{{field:<id>}}` / `{{hidden:<name>|fallback}}` tokens. Pipes referencing
  deleted fields are pruned automatically.
- **Hidden fields (URL parameters)**: creators declare parameter names
  (e.g. `utm_source`) form-wide in the builder; values are captured from the
  share link when a form loads (declared names only — arbitrary query params
  are never stored), submitted with the response, encrypted at rest exactly
  like answers, and shown in the response detail view. `?field_<id>=value`
  parameters prefill text-like input fields.

- Open-source contributor docs and community health files: `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `SECURITY.md`, issue/PR templates, `SUPPORT.md`,
  `GOVERNANCE.md`, `ROADMAP.md`, `CODEOWNERS`, and this changelog.
- `AGENTS.md` guidance files and `docs/ARCHITECTURE.md`.
- Continuous integration (`ci.yml`): backend and auth `pytest` suites plus
  webapp build/type-check and a Vitest test job, with self-hosted-runner
  preference and a MongoDB service for the backend tests.
- Dependabot configuration for weekly npm, uv, and GitHub Actions updates.
- Initial frontend test suite (Vitest + Testing Library) with a shared config.
- Mailpit for catching outbound email in local development.
- Backend: flow-native template gallery (Support triage, Lead qualification,
  Job application with screening) auto-seeded on every startup — idempotent,
  gated by `DEFAULT_SEED_FLOW_TEMPLATES`/`DEFAULT_WORKSPACE_ID`. See
  `backend/AGENTS.md` "Seed scripts" for the env vars and how to add more.
- Self-hosted product analytics: Umami now ships as a first-class Docker
  Compose service (its own Postgres, admin UI on `:3003`) instead of a
  BetterCollected-hosted default — no self-hosted deployment now silently
  phones home. Form views are attributed to a canonical
  `/{workspace_name}/forms/{slug}` path from the webapp regardless of
  client-host vs. custom-domain routing. See `backend/AGENTS.md`
  "Analytics (Umami)" and `plans/umami-self-hosted-form-analytics.md`.
- Umami website auto-provisioning: the backend now finds-or-creates its
  Umami website by name on startup, so self-hosters no longer have to log
  into the Umami UI and copy a website id into config by hand.
- `docker-compose.deployment.yml` hardening: real health checks (Mongo,
  Postgres, Temporal, backend, auth, Umami) with `depends_on:
  condition: service_healthy` gating, so services actually wait for their
  dependencies to be ready instead of just "started." `deploy.sh` now starts
  Umami too (previously missing) and auto-generates `UMAMI_APP_SECRET` on
  first run.

### Changed

- Corrected `docs/DEVELOPERS_GUIDE.md` to the current **uv + yarn** workflow.
- Rewrote `README.md` for a public audience.
- Sped up the backend test suite (~137s → ~5s) via session-scoped app/DB init.
- Aligned toolchain versions (Node via `.nvmrc`, Python for CI, `.editorconfig`).
- UI/UX: form titles are now shown across the app (forms list and form-detail
  header) with an "Untitled form" fallback, plus a "Forms" breadcrumb, and the
  form tab bar keeps the active tab in view.
- UI/UX: corrected page titles and empty/error states (Templates, Analytics,
  Integrations, Responders, Deletion Requests) and did a copy pass for typos,
  grammar, and consistent, inclusive second-person wording.
- UI/UX: Account Settings derives the avatar and name consistently and no
  longer prints the email twice; Custom Domain shows an explicit Pro upgrade
  prompt on free plans.
- Batched routine dependency updates across all services (npm + uv + GitHub
  Actions) and moved CI actions to Node-24 majors.

### Changed (trust-first design pass — responder form + builder)

- **Builder interaction pass** (per the measured builder audit): Insert /
  Text block / Logic are now real, always-visible actions (they failed AA
  contrast and unmounted entirely on the welcome/thank-you pages — new
  creators saw no way to add a question); a quiet "Saving… / Saved /
  Couldn't save" indicator finally reports autosave state; clicking a title
  places the caret at the click point instead of selecting the whole title
  (one keystroke from data loss before), and the toolbar size readout shows
  the real 24px instead of "16"; page-rail thumbnails are legible schematics
  (first question + count) instead of slides scaled to 2.7px text; the page
  menu gained Duplicate (with internal logic/piping references correctly
  remapped to the copy's own fields — the previous duplicate implementation
  left them pointing at the original page) and a consequence-stating delete
  confirmation; the canvas gained Fit/100% zoom; the properties drawer is
  300px with a "‹ Back to page" affordance and Esc-to-deselect; Publish wears
  trust blue and the help button dropped its amber.
- **Trust & privacy authored in the builder** (Design-Language §4): a new
  drawer section sets the form's purpose, plain-words retention, and privacy
  policy link with a live preview of the responder-facing trust strip; the
  values persist as workspace-form settings and render on every step of the
  published form.
- **Submission detail joins the portal's design**: opening a receipt (and
  requesting deletion) landed on a bare white page with its own tab style —
  a different product right where responders exercise their data rights. It
  now wears the portal's clothes: surface wash, a white receipt card with
  the same identity as the list (form title, mono receipt number, exact
  time, Anonymous chip, deletion status), portal tabs renamed to responder
  language ("My response" · "Privacy & deletion"), and the deletion section
  restated as a calm trust surface — shield statement of the right, a muted
  "Request deletion" button with an expectation-setting caption, and an
  amber "Deletion requested · Pending" state instead of a red warning. The
  page also stopped wearing the platform's brand: the bettercollected
  wordmark header (a jarring brand switch inside the workspace's own
  branded space, especially on custom domains) gave way to the workspace's
  avatar + name linking back to the portal, with the platform down in the
  same quiet "Powered by" caption the portal uses.
- **Anonymity now holds at the account level**: verifying your email no
  longer links anonymous submissions to your account — My submissions and
  Deletion requests list only identified responses, and an anonymous
  response is reachable solely through its submission number, which is what
  the portal copy promises ("that's what keeps it anonymous"). A caption
  under the list says where anonymous submissions live. Also from this
  feedback round: confirm dialogs' dismiss action is a quiet outline button
  (the filled near-black "No" read as a second primary), the deletion
  confirmation says what it does ("Ask the workspace to delete this
  response?" · Cancel / Request deletion — no more Yes/No) and states the
  consequence; and opening a submission no longer hops through a redirect
  (receipts and number-search link straight to the response tab) nor
  flashes a white full-screen loader (the workspace-branded shell stays up
  with a skeleton while loading).
- **Anonymous responders can finally exercise their deletion right** (bug):
  requesting deletion authorized only `dataOwnerIdentifier == user` (plus
  admins) — an anonymous response has no owner identifier, so the very
  people the product promised anonymity to were 403'd out of deleting their
  own response; the check now accepts the anonymous identity hash. Deletion
  requests also store that hash, so anonymous requests actually appear in
  the responder's Deletion requests tab (they used to vanish after
  creation). My submissions now surfaces "Deletion requested / Deleted"
  status on the affected receipts (the list previously looked unchanged
  after a request), deletion-request cards carry the receipt number and an
  honest "Requested:" timestamp, the request button no longer nests a
  button inside a tooltip's button (hydration error), and the danger button
  uses the design language's muted red instead of washed pink.
- **Responder portal redesigned as the trust surface it links from**: the
  workspace portal (where every form's "view or delete your response
  anytime" promise lands) was an admin-dashboard reskin. Form cards now
  speak responder language — the form's purpose and question count instead
  of a provider glyph and a tautological "Public" chip. Submission receipts
  are finally identifiable: mono receipt number, exact time, and an
  Anonymous shield chip (they used to show only title + date, so repeat
  submissions were indistinguishable). The workspace card carries the trust
  anchor; search-by-submission-number reads as the right-of-access feature
  it is (trust treatment, labeled controls) instead of clip-art; the
  deletion-requests empty state explains the right and the path to exercise
  it; tabs, wash, avatar fallback and body ink moved onto the design
  tokens; "Terms Of Services" typo fixed; the pink submission-detail title
  and the "Form Page ‹ My response" breadcrumb cleaned up.
- **The builder now loads the draft it edits** (data-trust bug): the edit
  page's loader requested the form with `published=true&draft=true`, and the
  API returns the latest *published* version whenever one exists — so
  autosaved changes (theme, welcome description, …) looked lost on every
  reload while the draft in the database was actually correct. The builder
  loader now fetches the draft.
- **One form footer**: "Powered by bettercollected" moved into the trust
  strip as its last item (gated by the existing disable-branding setting,
  which the old footer never honoured) — the thank-you page's own floating
  footer sat underneath the fixed strip and the two overlapped.
- **Thank-you heading is customizable**: the hardcoded "Thank You! 🎉" is now
  an editable (and pipeable) title on the thank-you page — edited inline in
  the builder like the welcome title, persisted on the form, with the
  classic greeting as the default when unset.
- **Responder form transitions unified**: every page type declared its own
  animation — different easings, and no exit motion at all, so the old page
  froze in place while the new one slid over it — and the ±100% fly-in was
  never clipped, flashing a horizontal scrollbar on every step. One
  direction-aware transition now covers welcome/pages/thank-you (entering
  page slides the full width, exiting page drifts a quarter-width the other
  way while fading), the container clips the motion, and
  `prefers-reduced-motion` gets a plain cross-fade.
- **Builder canvas works on large screens**: the canvas mat collapsed to a
  content-height band floating in white void on tall viewports (the layout
  row centres its children and the mat, unlike the drawer, never stretched)
  — and the collapsed height fed back into the Fit computation, shrinking
  the slide further. The mat now stretches to the workspace, and Fit no
  longer caps at true size, so on big monitors Fit fills the mat while 100%
  shows the true 1440×810 — the toggle was a no-op there before.
- **Flow view feedback round**: the Insights header no longer contradicts the
  node chips — it now labels its two instruments apart ("17 responses"
  behind the node/edge counts vs "journeys: 13 started · 11 finished" from
  anonymous navigation tracking, with tooltips explaining each); the side
  panel shows the selected page's full question (it was CSS-truncated to one
  line); the "Edit content" overlay was rebuilt on the main canvas's
  measured-scale layout — exactly centred sheet on the mat, page-number
  eyebrow + full-title header, live Saving…/Saved status instead of a static
  "changes save automatically" claim, and the standard 300px drawer; and
  edges are now set one frame after nodes when the graph re-derives —
  React Flow silently drops edges whose handles aren't mounted yet, which
  intermittently rendered the whole graph unlinked.
- **Flow (Logic) view brought onto the design language**: the `brand-*`
  Tailwind ramp — which still peaked at the old bright blue and leaked into
  every "tokenized" surface using brand classes — was retuned to trust blue,
  recolouring the flow view's jump edges/dots/labels, selected nodes and
  buttons (and the last old-blue surfaces product-wide). Node eyebrows were
  hairline-on-white (1.4:1 — illegible) and 11px metadata was below AA; both
  now legible ink. Destructive red and the drop-off chip use the muted
  design tokens. Interaction fixes: the graph re-fits after mount so the
  Start node no longer opens clipped under the header; the connect dots —
  the view's primary gesture — are visually larger with a ~2× invisible hit
  area; empty pages get an amber "empty page" warning chip (they read
  identically to real pages before, and responders would hit a blank page);
  deleting a jump edge now offers an 8-second Undo toast (a rule can carry
  several conditions — one keystroke shouldn't silently discard it), which
  also fixed the shared toaster ignoring per-toast durations; the minimap
  only appears once the graph outgrows a screenful; React Flow's zoom
  controls are themed; and the autosave Saving…/Saved indicator now shows in
  the flow header, where the navbar's is hidden.
- **The trust strip is visible while building**: every builder slide now
  renders the responder-facing trust footer (collected-by, purpose,
  retention, privacy link) exactly where responders see it, live-updating as
  the Form-tab fields change; while the trust content is empty, a nudge on
  the canvas names what responders see and deep-links to the Form tab —
  creators shouldn't need to publish to know what privacy story their form
  tells.
- **Form themes are contrast-verified** (WCAG 2.1, computed): 10 of 13 named
  themes rendered buttons whose white text failed AA (Green was 2.3:1, Yellow
  1.9:1), every theme's input borders failed the 3:1 non-text minimum, and
  Teal's question text failed even AA. Each palette was retuned against how
  the roles are actually used — question text on the accent ≥ 7:1 (AAA),
  white-on-button ≥ 4.5:1, input borders ≥ 3:1 — keeping each theme's hue.
  The Design tab now shows each theme as an honest miniature form (question
  ink on the accent, bordered input, button with white text) in a proper
  full-width card list, so the real contrast is visible before choosing.
- **Builder canvas centring rebuilt**: Fit scaled the slide with
  window-arithmetic (`100vh` boxes, `transform-origin: top left`) whose
  layout box disagreed with the visible card, so the sheet drifted
  off-centre depending on viewport size. The scale is now measured from the
  canvas mat itself and the wrapper's layout size equals the scaled card's
  visual size — exactly centred on both axes at every window size; 100%
  edits at a true 1440×810 with scrolling.
- **Builder drawer split into Page · Form · Design**: form-wide settings
  (hidden fields, trust & privacy) moved out of the Page tab — which had
  grown into one undifferentiated scroll — into their own Form tab, also
  making them reachable from welcome/thank-you pages; Page-tab section
  spacing tightened.
- **Builder chrome speaks the design language** (second builder pass): the
  neutral `black-*` Tailwind scale was retuned from flat Bootstrap grey to
  the blue-biased ink/hairline tokens, so builder and dashboard chrome cohere
  with the responder form; the Insert Field picker dropped its pastel-rainbow
  tiles for one quiet white-tile grid with ink icons; layout and theme
  selection use trust blue (they were Tailwind pink-500 and the old bright
  brand blue) and layout thumbnails gained legible glyphs plus captions
  ("Left aligned", "Image right", …); drawer tabs are a segmented control
  instead of a near-black pill; the page rail uses one labelled-card grammar
  for welcome/content/thank-you pages; selecting a field shows a toolbar
  (field-type chip · duplicate · delete) instead of a lone floating trash
  can, backed by a new duplicate-question action; the Page drawer is grouped
  into "This page" / "Whole form" scopes; the canvas sheet sits on a real
  elevation shadow; and the builder Preview (desktop and mobile) now renders
  the trust strip — it previously omitted the very thing the drawer promises
  responders will see.

- **Form details page (dashboard) redesigned**: the 8-tab bar — which silently
  overflowed and hid the Form Link and Analytics tabs entirely on desktop —
  is now 5 always-visible tabs (Preview · Responses · Analytics · Share ·
  Settings). Deletion requests became a segment inside Responses; Visibility
  and Integrations became Settings sections (old URLs redirect); tabs use a
  single active affordance with count badges. The header gained a real
  breadcrumb and a plain-words meta line (Published/Draft chip, response
  count, provenance) in place of an unlabeled provider glyph; Share is the
  one primary action. Settings rows follow a label+description/control grid
  with dividers between (not inside) settings, a locked state for Pro-gated
  toggles, and a proper danger zone stating consequences. Preview shows
  labelled page cards that open the full-screen preview. Anonymous responses
  show a shield chip instead of "--"; creator-facing titles no longer leak
  answer-piping editor syntax; every tab pane sits on one horizontal grid,
  and pages end with a quiet "Version · Open form" line.

- **Responder form redesigned to the trust-first design language**: questions
  now render at 24px/600 ink and answers at 16–18px ink (the input no longer
  out-shouts the question, and answers no longer render in link-blue); every
  field type shares one bordered white input with a visible themed focus ring
  (short/long-text fields had regressed to an underline with no focus
  indicator); the default theme is a calm neutral surface (`#F6F8FC`) with
  trust-blue actions (`#2456CC`) instead of the full-bleed pale-blue wash
  (saturated themes remain opt-in); buttons say what happens ("Continue",
  "Submit response") at proper weight; a provenance chip + "Page x of y"
  progress meta sits where the eye starts; the trust strip is legible (13px)
  and links "How your data is used" and "View or delete your response".
- **Builder**: the slide canvas now sits on a neutral mat as a bordered white
  card (figure/ground for the thing being edited); the title editor matches
  the responder's 24px question scale (honest WYSIWYG); panel section headers
  share one 12px-caps rhythm; empty pages show an "Add a question" affordance
  that opens the Insert menu; piping chips use the trust palette.

### Fixed

- **Workspace settings: React error fixed and given a discoverable home.**
  Opening the settings sheet errored (`value` prop on `input` should not be
  null): the privacy-policy and terms URLs fed null into controlled inputs
  (title/description already had fallbacks). The save diff also compared
  snake_case keys against the camelCase DTO, so those two fields were sent on
  every save whether changed or not — both fixed. Settings was reachable only
  through an unlabelled translucent pencil on one page; it's now a
  first-class "Workspace settings" item in the sidebar's administration
  cluster (above Members), and the contextual pencil on the details card is a
  bordered, titled button.
- **Field spacing on form pages brought down to a readable rhythm.** Question
  groups sat 120px apart for responders (desktop) and 80px in the builder —
  10–15× the 8px gap inside a group, so question–input pairs stopped reading
  as neighbours and a 6-question page showed ~3. Now 48px mobile / 64px
  desktop everywhere (builder canvas, live form, preview thumbnails), so the
  builder is honest WYSIWYG. Also removed the builder's per-row `h-full`
  (each field stretched to an equal share of the slide, so spacing changed
  with field count) and its doubled padding (`py-[10vh]` + `px-6` twice on
  top of the layout's own 60px).
- **Form preview modal rebuilt.** "Open preview" opened on a dark "please use
  the desktop version to edit this form" banner (a mobile-editing message, in
  a preview, on desktop) above an empty nav strip, and the `aspect-video
  h-full` stage pushed the form card past the bottom of the screen. The
  preview now has one quiet header — Back, the form title with a Preview
  chip, the honest "Answers aren't saved" note, and Share/Publish — over a
  centered 16:9 stage sized to fit both viewport dimensions (mobile fills the
  screen, as a responder would see it).
- Responder portal (and its dashboard mirror): the "Find a response by its
  number" card moved from a third column on wide screens into the left
  sidebar, below the identity section — one utility column, a consistent
  two-column layout at every width, and no more modal fallback below xl.
- **One vocabulary: workspace + site.** The product used three overlapping
  terms — onboarding created an "Organization", the dashboard managed a
  "workspace", and the responder-facing surface was a "Public Workspace" (or
  internally, the "responder portal"). Now: the **workspace** is where you
  work; your **site** is what the world sees ("Site" as the nav label, "your
  site" in running copy). Onboarding says "Create your workspace /
  Workspace name"; settings copy, custom-domain copy ("Serve your site from
  a domain you own"), template visibility, and the sign-in feature line all
  speak the same two words. "Organization" survives only where it means the
  real-world entity. The settings surface follows the scheme too: "Workspace
  Settings" is now **Site settings** (it configures exactly what the world
  sees), with **Identity** and **Link & domain** tabs replacing "Workspace
  Details" / "Manage URLs" — renamed in the sidebar entry and the frame's
  gear as well.
- Workspace settings: the Privacy Policy URL and Terms of Service URL inputs
  are full-width, capitalized, and validated on save — values must be real
  http(s) links (a missing scheme is forgiven by prepending https://;
  whitespace, non-web schemes like javascript:, and scheme-less non-domains
  are rejected with "Enter a full link, like https://yoursite.com/privacy").
  These values render as links on the public workspace and in every form's
  trust footer, so bad values were a broken-trust-link (or script-injection)
  vector.
- **Workspace settings audited against the trust language.** Copy rewritten
  in plain speech: the Title-Case marketing header ("Tailor Title, Refine
  Description… and Elevate with a Banner Image") now says what the page is
  ("The identity responders see on your public workspace"); "Organizations
  Title"/"Organization Descriptions" became "Workspace name"/"Description";
  the policy-URL fields explain their trust role (linked from the public
  workspace and every form's trust footer). One left edge for header, tabs
  and panel content — the panels used to stack their own px-20+ on top of
  the container's, indenting content past the tabs. Manage URLs was
  reorganised into two honest sections: the workspace link (mono URL with
  trust-blue handle, Copy, Change link, and the stated consequence — "the
  old link stops working") and Custom Domain, which no longer shows free
  users a domain form that only bounced them to the upgrade modal — the
  upgrade note is the whole section. Validation copy tells you what to type
  ("try something like forms.yoursite.com") in muted red, warnings in amber;
  Save is the trust-blue primary instead of near-black.
- Workspace settings now open **inside the Public Workspace frame** (behind
  the address-bar gear, with a highlighted gear state and a "Back to page"
  return) instead of a bottom sheet over the whole app — edit, save, and
  you're looking at the page you just changed. The sidebar "Workspace
  settings" entry routes to this view; the settings surface was extracted to
  a shared component so the URL-update deep links that still use the bottom
  sheet render the identical content. Inside the frame the settings' own
  URL-actions row is hidden (the address bar already carries it).
- **The dashboard's "Public Workspace" page is now a true mirror of the
  responder portal.** It rendered admin-style form cards (provider icon,
  "Public", response counts, edit/share affordances) — not what responders
  see. It now renders the portal's own components: the same three tabs
  (Forms · My submissions · Deletion requests), the same receipt-search card
  (with the portal's below-xl modal fallback), forms with purpose line,
  question count and pinned chip, with the page title matching the sidebar
  entry. Clicking a form opens the real public form on the client domain in
  a new tab, exactly as a responder experiences it. The mirror sits inside a
  browser-style frame that says what this is — a page that lives at a URL:
  the chrome carries the real public address with copy and open-live
  actions, plus the workspace-settings gear, so creator controls live on the
  frame and never inside the mirrored content (the old settings pencil
  floated over the details card, which responders never see; the separate
  Workspace Link card was absorbed by the address bar). Deliberately NOT
  mirrored: the portal's identity furniture (verify-email card, responder
  account card, powered-by caption) — redundant or misleading inside the
  signed-in dashboard. Also fixed a React warning the fulfilled
  deletion-request card tripped everywhere it renders (`href=""` spread onto
  a plain div).
- **Dashboard chrome brought onto the trust palette.** The sidebar's "Public
  Workspace" link was blue→pink gradient text (the retired "playful" rainbow,
  with no measurable contrast) and the "Pro" badge was an orange-gradient pill
  with ~2.1:1 white-on-orange text in a one-off display face — both are now
  quiet chips/links on the trust ramp. Sidebar selection had two bugs: exact
  URL matching meant nested routes (Responders, Members subpages) highlighted
  nothing, and the selected state was grey — now prefix-matched and trust-blue
  tinted like every other selected state. Old bright-blue (`#0764EB`,
  `blue-600`), slate/gray neutrals, Bootstrap greys in the account dropdown,
  and the alarmist red Logout were retuned to the ink ramp and muted red; the
  account dropdown avatar now falls back to the email initial instead of an
  empty square. Page tabs (Members, Responders and Groups) use the trust-blue
  underline; all admin data tables share hairline borders, surface headers and
  ink text; duplicated page titles (sticky bar + in-page h1) collapsed to one.
- **Upgrade-to-PRO modal made honest (no-dark-patterns law).** The headline
  promised "PRO is Free" / "You won't be charged any money" while a footnote
  said "Free for 90 days!" — and the upgrade has no expiry in code at all. It
  now makes one claim ("currently free — no card needed and nothing is
  charged"), the button says what it does ("Activate PRO for free"), the
  pastel-rainbow feature cards became one calm treatment, and the feature
  copy was corrected ("as many forms as you want", "separate workspaces for
  different teams, organizations, and projects").
- Copy: form cards pluralize response counts ("0 Responses"); the responders
  page explains the list in plain language and states the responder's rights;
  the groups empty state reads "Create a group to control who can access your
  forms"; members rows no longer print the same email twice.
- **Deletion requests were impossible to fulfil from the dashboard.** The only
  delete affordance — a kebab menu inside the response drawer — was rendered
  with a literal `hidden` class, and even unhidden it deleted permanently with
  no confirmation. Pending rows in the Deletion requests table now carry a
  first-class "Delete response" action (plus a quiet "View") that routes
  through a consequence-stating confirmation dialog; the drawer kebab is
  visible and uses the same confirm. Deleting now refreshes the table and the
  pending counter (the mutation didn't invalidate the queries feeding them),
  the status chip speaks the trust palette (amber Pending / green Deleted —
  it was error-red, and a dead code path labelled fulfilled requests
  "Expired"), fulfilled rows show the deletion date instead of "Not deleted
  yet" beside a Pending chip, rows carry the submission receipt number so
  anonymous requests can be matched to what a responder quotes, and the
  header counter reads "N of M requests pending" instead of the quota-like
  "5/5 deletion remaining".
- The response drawer rendered blank question labels outside a form page:
  the fetched form was never passed down, so titles and pipe resolution fell
  back to the (empty) redux form. All VIEW_RESPONSE openers now pass the
  form — question titles render, answer pipes resolve with that submission's
  answers, legacy fields whose text lives in `value` (null rich-text title)
  show their real question instead of the "Enter Question" placeholder, and
  unanswered file-upload fields say "No answer" instead of an empty grey box.
- Responders table rows drifted out of alignment: the "frozen" Responder ID
  area was faked with two independent tables whose row heights were never
  guaranteed equal (two-line identifier cells vs. one-line answers, against a
  forced 48px row height). Rebuilt as a single table with CSS-sticky leading
  columns — alignment holds by construction, the whole row shares one hover
  and click behaviour, and the header scrolls in lockstep (fixed header +
  frozen columns verified through full horizontal and vertical scroll).
- Form details page: the Deletion Requests empty state showed the responses
  copy ("No responses yet" on a form with responses); "bettercolleceted"
  typo in the branding setting; preview cards had a pointer cursor but no
  click behaviour and didn't survive window resizes.
- **Identity sharing is now opt-in, and anonymity is actually enforced.** The
  "Show your identity" checkbox on the submit step arrived pre-checked
  (contradicting the no-dark-patterns design law) — it now starts unchecked,
  in a legible 15px consent container. Worse: the backend accepted the
  `anonymize` flag but never honoured it — "anonymously submitted" responses
  still stored the signed-in email as `dataOwnerIdentifier`. Anonymous
  responses now store no owner identifier and no email, only a one-way hash
  (`anonymous_identity`) so the responder can still find and delete their own
  submission.
- Builder `useFormState` setters spread a stale render-time snapshot instead
  of the current state, so mount-effect writers (theme, welcome description)
  could silently wipe keys written between render and effect — this ate the
  form title and hidden-field list under hot-reload/multi-writer conditions.
  All setters now use functional updates.
- Umami pageview double-counting: automatic tracking is now disabled
  (`data-auto-track="false"`) and public form views send only the explicit
  canonical-path event — previously every form view would count twice (auto +
  canonical), and dashboard activity was tracked too. The tracker is also
  rendered as a plain deferred `<script>` (not `next/script`), so analytics
  loads even if client-side hydration stalls, and the canonical event now
  waits for the tracker script instead of being dropped when it loads late.
- Local dev: `nginx-local.conf` didn't forward WebSocket upgrades, so Next.js
  dev-server HMR fell back to a `/_next/webpack-hmr` 404 polling loop through
  the proxied hosts (`:3001`/`:3002`) and pages could stall on a loader
  without hydrating.
- React 19 form-rendering crash and DOM-prop console errors in the webapp.
- React 19 DOM-prop warnings from data tables (`react-data-table-component` v8).
- Form editor no longer auto-saves on load — only on real user edits.
- Invalid nested `<button>` in the form-published modal.
- Analytics now distinguishes a genuine load error (with a retry) from an
  empty state.
- Backend Umami client (`umami_client.py`): error paths raised a raw
  `TypeError` instead of a clean HTTP error (the app's custom `HTTPException`
  takes `content=`, not `detail=`); a failed retry after a 401 also went
  unchecked instead of surfacing a clean error.
- Form analytics `/stats` endpoint 500'd against current self-hosted Umami's
  response shape (flat ints + a `comparison` object, not nested `{value,
  prev}` per metric) — surfaced once Umami was actually reachable end-to-end.
- Local dev: `nginx-local.conf` 502'd on the client-host/custom-domain ports
  (e.g. a form's share URL) because it proxied to `localhost:3000`, which
  inside the nginx container isn't the host where webapp/backend actually run.
- `docker-compose.deployment.yml`: Temporal's `DB=postgresql` was never a
  valid driver name (`temporalio/auto-setup` only accepts `postgres12`,
  `postgres12_pgx`, `mysql8`, `cassandra`) — Temporal has likely never
  started successfully via this compose file; this only surfaced once a real
  health check was added instead of just checking the container was running.
  Also pinned `postgres:latest` (temporal's Postgres) to `postgres:15-alpine`
  and moved it to a named volume — an unpinned tag had already drifted to
  Postgres 18, which refuses to start against an older major version's data
  directory.
- `install.sh` referenced Poetry and a per-service `Makefile`, neither of
  which exist anymore since the Python services moved to `uv` — the script
  was fully broken. Rewritten to `uv sync` per service.
- Backend boots without an `OPENAI_API_KEY` (OpenAI client is created lazily).
- Forms listing/pagination failure (fastapi-pagination under Starlette 1.x).
- Login "Failed to send OTP" flow (route, API host, and cookie-domain issues).
- Numerous Dependabot security advisories across all services.

### Security

- Removed committed Stripe/Sentry secrets from `auth/.env.example` (placeholders
  now). **Note:** these values still exist in git history and should be rotated
  and scrubbed before/at public release — see `SECURITY.md`.

## [2.2.0] - 2026-02-27

- Baseline for this changelog. See the
  [v2.2.0 release](https://github.com/bettercollected/bettercollected/releases/tag/v2.2.0)
  and earlier tags for prior history.

[Unreleased]: https://github.com/bettercollected/bettercollected/compare/v2.2.0...HEAD
[2.2.0]: https://github.com/bettercollected/bettercollected/releases/tag/v2.2.0
