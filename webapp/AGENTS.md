# webapp/AGENTS.md

Scoped guidance for the **frontend**. Read the root [../AGENTS.md](../AGENTS.md) first.

## Role

The entire user-facing UI: form builder, workspace dashboards, responder/fill-form portal, submissions, templates,
integrations import, billing/pricing, onboarding. Next.js 14, served on **:3000** (also logically serves the client
host on `:3001/{workspace_handle}` and custom domains on `:3002` behind nginx).

## Stack notes that will trip you up

- **Dual router, mid-migration.** Both the legacy **Pages Router** (`src/pages/`) and the newer **App Router**
  (`src/app/`) are live at once. New form-editor routes are in `app/`; much else is still in `pages/`. Check which
  router owns a route before adding pages — don't duplicate.
- **Layered styling.** Tailwind (`tailwind.config.ts`, heavily customized) **+** MUI 5 + Emotion + styled-components
  **+** shadcn/ui (`src/shadcn/`, Radix primitives). Match the styling system already used in the file you're editing
  rather than introducing a new one.
- **State:** Redux Toolkit + **RTK Query** for all server state; plain slices + **Jotai** atoms for client/ephemeral
  state; `redux-persist` for persistence; `redux-undo` in the builder.

## Directory map (`src/`)

```
pages/        # Pages Router routes incl. tenant-scoped [workspace_name]/ ; api/ (Sentry tunnel, unsplash)
app/          # App Router routes (dashboard, forms/[form_id]/edit|preview) + _dispatcher/ client hydrators
store/        # Redux store + slices + RTK Query API slices + customFetchBase.ts (auth/refresh)
Components/   # ~45 feature UI folders (FormBuilder, Form, dashboard, Workspace, RespondersPortal, Modals, ui, ...)
views/        # atomic design: atoms / molecules / organism
containers/   # smart containers (form-builder, dashboard, Onboarding) + ReduxWrapperAppRouter.tsx
lib/          # builders/ (form-builder engine: managers, listeners), hooks, event-bus
shadcn/ shared/ layouts/ Contexts/ models/ types/ constants/ configs/ utils/ mock/(MSW) stories/(Storybook)
```

## Talking to the backend — always via RTK Query

- All API slices target `environments.API_ENDPOINT_HOST` (`src/configs/environments.ts`, default `/api/v1`).
- **Do not add ad-hoc `fetch`/axios calls.** Add an endpoint to the right RTK Query slice under `src/store/` and use
  the generated hook. ~16 slices exist: `authApi`, `workspacesApi`, `formsApi`, `providerApi`, `importApi`,
  `analyticsApi`, `integrationApi`, `plansApi`, `couponCodeApi`, `templateApi`, `mediaLibraryApi`, `consentApi`, etc.
- **Auth is cookie-based.** [src/store/customFetchBase.ts](src/store/customFetchBase.ts) sets `credentials: 'include'`
  and runs a **mutex-guarded silent refresh** on `/auth/refresh_token` when it sees "You are not logged in", then
  retries. Don't bypass `customFetchBase` for authed calls.
- SSR vs browser split: server-side code uses `INTERNAL_DOCKER_API_ENDPOINT_HOST` (`next.config.js`).

## Feature flags

`next.config.js` `publicRuntimeConfig` exposes many `ENABLE_*` flags (`ENABLE_FORM_BUILDER`, `ENABLE_V2_BUILDER`,
`ENABLE_TYPEFORM`, `ENABLE_GOOGLE`, `ENABLE_EXPORT_CSV`, `ENABLE_RESPONSE_EDITING`, `ENABLE_BRAND_COLORS`, ...).
Gate new UI behind a flag when it mirrors an existing gated feature. A feature may be built but flagged off.

## The form builder

Drag-and-drop engine in `src/lib/builders/` (managers + listeners), editor state in `src/store/form-builder/`
(`builderSlice` with actions/selectors/utils), UI in `Components/FormBuilder` + `containers/form-builder`.
A **V2 builder** exists behind `ENABLE_V2_BUILDER`, wired into the App Router edit/preview routes. Form data conforms
to the backend **StandardForm** shape — keep field types in sync with `common/common/models/standard_form.py`.

**Answer piping + hidden fields (v2):** question titles can embed earlier answers or URL parameters. A pipe is an
inline `answerPipe` TipTap node (`src/utils/richTextEditorExtenstion/answer-pipe.ts`, inserted via the "@ Answer"
menu in the title toolbar); plain-text surfaces (descriptions, thank-you message) use `{{field:<id>}}` /
`{{hidden:<name>|fallback}}` tokens. The resolver lives in `src/utils/answer-piping.ts` and reads values through the
same `getComparableAnswerValue` as conditional logic — extend both together. Hidden-field *names* live on the form
(`StandardFormDto.hiddenFields`, edited in the page properties drawer, form-wide); *values* are captured from the
share link's query string on the public form page (declared names only), held in
`src/store/jotai/responder-hidden-fields.ts`, submitted as `hidden_fields`, and encrypted at rest like answers.
`?field_<fieldId>=value` URL params prefill text-like input fields. Deleting a field/hidden name prunes its pipes
(`pruneOrphanedPipes`, called next to `pruneOrphanedConditions`).

**Field rules (respondent runtime):** a question's `properties.rules` (require / read-only / set value / change
title or description while a condition or formula holds) are evaluated by `src/lib/field-rules.ts`, the pure
twin of backend `services/field_rules.py` (no `eval`; same operator table, caps, ordering and evaluation budget).
Shared cases: `docs/spec/field-rules.cases.json` and the `fieldRules` cases of
`docs/spec/answer-validation.cases.json`, run on both sides, so change one evaluator only together with the other.
`useDerivedAnswers` (`lib/hooks/`) writes calculated and set values into the answers; `useFieldRuleStates` gives
`QuestionWrapper`, `validateSlide` and the answer/date-rule checks the effective required flag and the locked
questions (read-only, not disabled; a locked question is never required and meets no answer or date rules). The
page's status region (`field-rule-announcer.tsx`) says once, politely, what an answer changed. A form without rules
takes none of these paths. The server stays authoritative.

**Review page (respondent runtime):** a form with `settings.showReviewPage` (builder: Form tab, "Before sending") ends
in a page of its own instead of submitting from the last page. It is a place in the journey like the welcome page and
the ending: `REVIEW_SLIDE = -3` in `utils/review-page.ts`, drawn by `views/organism/form/review-page.tsx`, never
stored or sent before submit. `reviewSections` lists the pages of the visited path (`history`) from the answers
`normalizeGroupAnswersForSubmit` gives (what the submit sends): logic-hidden, internal and hidden-field values are
left out, rule-set values are marked, files show their name. "Edit" (`editFromReview`) goes to a page and keeps the
reviewed path in `reviewPath`; its "Back to review" replays the whole path from its first page with `walkReviewPath`
(back to the review over the route as it now runs, on at a page never seen, or to a page that is no longer
complete). The review does not change what is sent: answers to hidden questions and files are still sent by design,
so `alsoSentRows` names them in an "Also sent" block, with the link's hidden-field values on a line of their own. Sending lives in `use-finish-form.ts`,
shared by the last page and the review (409 closed/not open/full keep the answers; 422 goes to the page). A page is
complete by `pageInvalidations` (`utils/page-validation.ts`) everywhere.

**Field rules (builder):** the inspector's Rules section (`views/molecules/form-builder/field-rules-section.tsx`, the
editor in `field-rules-settings.tsx`) writes rules through the `set_field_rules` op, so the ops engine's handler
(`lib/form-ops/handlers/rules.ts`) and the shared checks (`lib/form-ops/field-rule-checks.ts`, twin of the
server's `field_rule_problems` and `prune_field_rules`) decide what is accepted, and each edit is an undo step.
The same checks give the editor's inline warnings. Structural ops (remove, make internal, move across a group,
remove or replace options) drop the rules they leave dangling and say so in their result; duplicating a page does
not copy rules. The section shows only while `FIELD_RULES_ENABLED` is on for the webapp (`useFieldRulesEnabled`,
read per request like `SSO_ENABLED`, `lib/runtime-flags.ts`); with it off, existing rules are listed read-only. A
save the server refuses with 422 `field_rules_disabled` toasts the reason (`audo-save-form.tsx`). The formula box is
shared with calculated fields (`formula-input.tsx`).

**Choice logic (respondent runtime and builder):** a choice's `logic` and a question's `properties.optionFilter`
(which options are offered; `utils/option-logic.ts` is the pure twin of backend `services/option_logic.py`, its structure,
save checks, repair and warnings are in `utils/option-logic-checks.ts`; shared cases `docs/spec/option-logic.cases.json`)
are evaluated by `optionStates`. `useOptionStates` (`lib/hooks/use-option-states.ts`) hands the choice components the
available options (radios, checkboxes and the dropdown render only those: `offeredChoices`), `QuestionWrapper` and
`validateSlide` treat a question with nothing to choose as optional, and `useClearUnavailableOptions` (called next to
`useDerivedAnswers` in `form-slide.tsx`) clears a selection that stopped being available, from the answers as a submission
carries them; the question says so in `option-cleared-notice.tsx` (a polite status region under its options). The builder
edits an option's logic and a question's filter in `form-builder/option-logic-settings.tsx` (Logic section of a choice
question; the existing `ConditionRow`), with the shared warnings; `pruneOrphanedConditions` also runs `pruneOptionLogic`, so
every structural edit repairs option logic as the server's save does (and autosave tells the creator what the server
repaired: `droppedOptionLogic`). Page-level choice questions only. The section shows only while `CHOICE_LOGIC_ENABLED` is on
(`useWorkspacePermissions().choiceLogicEnabled`, from the permissions answer like `fieldRulesEnabled`); with it off, existing
option logic is listed read-only. A copy of a question or page starts without option logic (`dropOptionLogic`). The server
stays authoritative (`hidden_option`).

**Save and continue later (respondent):** when the form's `settings.allowSaveDraft` is on, a question page offers "Save and
continue later" (`components/drafts/save-draft-control.tsx`, under the Continue button, never in the builder preview).
Signed in, it saves to the account; otherwise the respondent enters an address once and gets a link (the address is not
kept). The respondent API is `store/redux/drafts-api.ts` (token and edit key travel in the body, never a URL), the
browser's draft state is in memory only (`store/jotai/respondent-draft.ts`; the edit key rides the submit as `draft_key`
so the server deletes the draft). `components/drafts/draft-resume.tsx` (the `notice` of `RespondentPageShell`) reads the
link's `#resume=<token>` once, removes it from the address bar, and restores answers, hidden-field values and the page;
it says so when the form changed, closed or filled. The pure rules are in `utils/form-drafts.ts` (files and calculations
are never saved, positions are page ids). The privacy panel row and the builder setting (`form-draft-controls.tsx`, days
1 to 90) read the same settings; the ops engine and spec know `allowSaveDraft` / `draftRetentionDays`.

## Commands

```bash
yarn              # install
yarn dev          # :3000 (yarn dev-4000 for :4000)
yarn build        # prod build + next-sitemap postbuild
yarn lint         # next lint
yarn lint:fix     # eslint --fix
yarn format:check # prettier --check
yarn test         # jest (watch) + Testing Library + MSW (mocks in src/mock/)
yarn storybook    # :6006
```

## Gotchas

- **i18n:** locales `en` + `nl` (`next-i18next.config.js`); add user-facing strings via translation keys, not hardcoded text.
- **PWA + Sentry + APM** are wired in `next.config.js` / `sentry.*.config.js`; dev uses a separate `.next-dev` dist dir.
- **Multi-tenant routing:** most routes are under `[workspace_name]/`; respect workspace scoping and custom-domain logic
  (`Components/CustomDomain`) — a route that ignores the workspace handle will break client-host and custom-domain serving.
