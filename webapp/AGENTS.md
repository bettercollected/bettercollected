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
