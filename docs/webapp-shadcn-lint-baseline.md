# Webapp shadcn lint: baseline

The webapp has [`@shadcn/lint`](https://github.com/shadcn-ui/lint) wired into
`webapp/eslint.config.mjs` with **all six rules off**. This page records what each rule
would report today, so the decision which rules to enable (and at which level) can be made
from numbers. Nothing here changes `yarn lint`, which stays at its current 0 errors and
351 warnings.

## Wiring

- Dev dependency `@shadcn/lint`, pinned to an exact version (`0.2.1`). It needs Node 20.19
  or later; CI runs Node 22 (the repository-root `.nvmrc`).
- The plugin is registered for `src/**/*.{ts,tsx,js,jsx}`. It finds the components and the
  Tailwind theme through `webapp/components.json` (the `@app/shadcn/components` alias and
  `src/assets/css/globals.css`); no `settings.shadcn` is needed. The TypeScript parser comes
  from `eslint-config-next`.
- The rules are registered and set to `off`: `no-restyle`, `no-raw-colors`,
  `no-arbitrary-values`, `no-inline-styles`, `no-unknown-classes`, `require-static-classes`.
  With them off, lint time is unchanged (about 21 s for a full run on a developer machine).

### Checking new code against a rule

A rule can be run without enabling it, for example on the files you changed:

```bash
cd webapp
yarn eslint --rule 'shadcn/no-unknown-classes: warn' --rule 'shadcn/no-raw-colors: warn' src/path/to/file.tsx
```

## How the baseline was produced

One ESLint run over `webapp/src` with the six rules at `warn` through `--rule` flags (not
committed), on Node 22. Total: **2,927 findings in 349 files**. Of these, 184 findings in 24
files are in `src/shadcn/components/ui/*`, the design-system source itself.

## Per-rule summary

| Rule | Findings | Files | In `shadcn/components/ui` | In app code | Main cause |
|---|---:|---:|---:|---:|---|
| `no-unknown-classes` | 123 | 37 | 73 (7 files) | 50 | Typos, and animation classes no CSS defines |
| `require-static-classes` | 12 | 6 | 1 (1 file) | 11 | Template-literal `className` on a component |
| `no-raw-colors` | 242 | 71 | 47 (8 files) | 195 | 147 are SVG icon fills in `components/icons`; 48 elsewhere |
| `no-inline-styles` | 491 | 74 | 5 (3 files) | 486 | `style={{ ... }}`, many for dynamic values |
| `no-arbitrary-values` | 1,180 | 255 | 40 (16 files) | 1,140 | `text-[13px]`, `h-[56px]`, `bg-[#F2F4F7]` |
| `no-restyle` | 879 | 118 | 18 (2 files) | 861 | `className` on `Button`, `Label`, `TableCell`, `SheetContent`, ... |

### `no-unknown-classes` (123)

Classes the project's Tailwind cannot generate. The theme declares a closed spacing scale
(`src/assets/css/tailwind.css`), so steps that are not listed (for example `h-34`) do not
exist.

- Top files: `shadcn/components/ui/{alert-dialog,dialog,sheet}.tsx` (14 each),
  `components/ui/hamburger.tsx` (13), `shadcn/components/ui/{dropdown-menu,popover,select}.tsx`
  (10 each), `views/molecules/unsplash-image-picker/photo-card.tsx` (3).
- Top directories: `src/shadcn/components/ui` (73), `src/components/ui` (15),
  `src/views/molecules/unsplash-image-picker` (8), `src/views/molecules/dialogs` (3).
- The 73 in `shadcn/components/ui` are the `animate-in`, `animate-out`, `fade-in-0`,
  `zoom-in-95` and `slide-in-from-*` families used by dialogs, sheets, popovers and menus.
  No stylesheet in the webapp defines them (they came from `tailwindcss-animate`, which is not
  installed for Tailwind 4), so the enter and exit animations are probably not running. Worth
  checking in a browser before deciding between adding `tw-animate-css` or removing the classes.
- The rest look like genuine typos: `px-auto`, `sm:w-auo`, `fap-2`, `tex-black-800`,
  `text-md`, `items-s`, `align-center`, `space-between`.

Examples:

- `src/shadcn/components/ui/dialog.tsx:19`: `data-[state=open]:animate-in`
- `src/components/ui/hamburger.tsx:13`: `sm:w-auo` (suggested fix: nearby valid class)
- `src/views/molecules/unsplash-image-picker/photo-card.tsx:10`: `theme-border-default`

### `require-static-classes` (12)

A `className` on a component that is built dynamically, so the other rules cannot read it.

- Files: `views/organism/form-builder/outline/ending-options.tsx` (4),
  `views/organism/form-builder/outline/question-options.tsx` (4), and one each in
  `components/workspace/workspace-menu-dropdown.tsx`, `lib/hooks/use-dialog-modal.tsx`,
  `lib/hooks/use-secondary-dialog-modal.tsx`, `shadcn/components/ui/tooltip.tsx`.

Examples:

- `src/components/workspace/workspace-menu-dropdown.tsx:139`: dynamic `className` on `<Avatar>`
- `src/lib/hooks/use-dialog-modal.tsx:134`: dynamic `className` on `<DialogContent>`
- `src/views/organism/form-builder/outline/ending-options.tsx:64`: dynamic `className` on `<DropdownMenuItem>`

### `no-raw-colors` (242)

Hard-coded colors (`fill="#123FC9"`, `bg-[#F2F4F7]`) and class names that are not declared
theme colors (`bg-black-50`, `text-darkGrey`).

- Top directories: `src/components/icons` (102, of 147 in all of `components/icons`),
  `src/shadcn/components/ui` (47), `src/components/icons/flags` (25),
  `src/components/icons/brands` (20), `src/views/organism/form-builder/add-slide` (8),
  `src/views/organism/form-builder/fields` (7), `src/views/molecules/dialogs` (6).
- Top files: `components/icons/flags/usa.tsx` (20), `components/icons/brands/provider.tsx` (13),
  `shadcn/components/ui/calendar.tsx` (13), `shadcn/components/ui/badge.tsx` (11),
  `components/icons/empty.tsx` (9).
- 147 findings are illustration and brand-logo fills inside SVG components; replacing a flag or a
  provider logo with a theme token is not meaningful. Outside `icons` and `ui` there are 48
  findings in 28 files.

Examples:

- `src/components/icons/empty-form.tsx:8`: `fill="#C1DAFF"` (suggested: `var(--color-blue-200)`)
- `src/components/icons/brands/provider.tsx:30`: `fill="#4285F4"`
- `src/components/dashboard/empty-form.tsx:12`: `text-darkGrey` (not a declared theme color)

### `no-inline-styles` (491)

`style={{ ... }}` props and `<style>` elements.

- Top directories: `src/components/response-page` (76), `src/views/organism/form-builder` (57),
  `src/views/organism/form-builder/fields` (56), `src/views/molecules/responder-form-fields` (47),
  `src/views/organism/form` (39), `src/app` (38), `src/views/molecules/theme` (38).
- Top files: `components/response-page/read-only-question.tsx` (49), `app/global-error.tsx` (38),
  `components/response-page/read-only-form.tsx` (27), `views/molecules/theme/theme-shared.tsx` (27),
  `views/organism/form-builder/flow-view.tsx` (21).
- Many are legitimately dynamic (colors and fonts from a form's saved theme, drag positions).
  `app/global-error.tsx` renders outside the app's stylesheet on purpose.

Examples:

- `src/app/global-error.tsx:25`: inline `margin`
- `src/components/response-page/read-only-question.tsx:69`: inline `color`
- `src/views/organism/form-builder/flow-view.tsx:79`: inline `opacity`

### `no-arbitrary-values` (1,180)

Bracketed values such as `text-[13px]`, `h-[56px]`, `bg-[#F2F4F7]`. The message usually names
the on-scale equivalent, so many of these are mechanical.

- Top directories: `src/views/organism/form-builder` (143), `src/views/molecules/form-builder` (59),
  `src/components/form` (57), `src/components/workspace-sso` (57), `src/views/organism/form` (53),
  `src/views/molecules/theme` (50), `src/components/dashboard` (43),
  `src/shadcn/components/ui` (40), `src/components/datatable` (37).
- Top files: `components/workspace-sso/workspace-sso-section.tsx` (33),
  `components/datatable/form-options-dropdown.tsx` (31),
  `views/organism/form-builder/ai-chat-tab.tsx` (30), `views/organism/form-builder/slide-builder.tsx` (30),
  `views/organism/form-builder/flow-view.tsx` (29).

Examples:

- `src/components/form/breadcrumbs-renderer.tsx:14`: `h-[56px]` (suggested: `h-14`, same value)
- `src/components/auth/account-menu-dropdown.tsx:115`: `leading-[24px]` (suggested: `leading-6`)
- `src/components/template/template-settings.tsx:83`: `w-[18px]` (suggested: `w-4.5`)

### `no-restyle` (879)

`className` overrides on components that own their style. The plugin's built-in contracts are
strict (for example `Button` owns its spacing, `Label` and `SheetContent` allow no classes), and
none have been tuned for this project yet.

- Top directories: `src/views/organism/form-builder` (150), `src/views/organism/form-builder/fields` (91),
  `src/components/modal-views/modals` (56), `src/components/form` (35),
  `src/components/custom-domain` (30), `src/views/molecules/unsplash-image-picker` (24),
  `src/components/dashboard` (23), `src/views/molecules/theme` (23).
- Top files: `views/organism/form-builder/fields/tabular-input-field.tsx` (73),
  `views/organism/form-builder/welcome-page.tsx` (55), `views/organism/form-builder/thankyou-page.tsx` (52),
  `views/organism/form-builder/slide-options.tsx` (25), `views/molecules/theme/theme-type-shape-editor.tsx` (23).

Examples:

- `src/components/dashboard/form-settings.tsx:236`: `cursor-pointer` on `<Label>`
- `src/views/organism/form-builder/fields/tabular-input-field.tsx:122`: `border-b` on `<TableCell>`
- `src/views/organism/form/welcome-page.tsx:170`: `py-3` on `<Button>`

## Findings inside the design-system source

`src/shadcn/components/ui/*` produces 184 of the 2,927 findings (24 files): 73
`no-unknown-classes`, 47 `no-raw-colors`, 40 `no-arbitrary-values`, 18 `no-restyle`,
5 `no-inline-styles`, 1 `require-static-classes`. This is the source the rules describe, so
`no-restyle`, `no-arbitrary-values` and `no-inline-styles` should be turned off there when
those rules are enabled. `no-unknown-classes` is different: the animation classes are worth
fixing at the source, not excluding.

## Recommended adoption order

Enable rules by how few and how clearly wrong their findings are. Each step is its own pull
request; nothing in the list is done yet.

1. **`no-unknown-classes` as `error`.** 123 findings, of which 50 in app code are typos that
   generate no CSS. Fix those, decide the animation classes in `shadcn/components/ui` (add
   `tw-animate-css` or remove them), then enable. Likely a real bug fix, not just hygiene.
2. **`require-static-classes` as `error`.** 12 findings in 6 files. Cheap to clear, and it keeps
   the other rules able to read component classes.
3. **`no-raw-colors` as `error` for app code, off for `src/components/icons/**` and the `ui`
   folder.** 48 findings in 28 files remain after those two exclusions.
4. **`no-inline-styles` as `warn`, with a burn-down.** 486 in app code. Decide first how
   dynamic theme values are expressed (CSS custom properties set on a wrapper), and exempt
   `app/global-error.tsx`.
5. **`no-arbitrary-values` as `warn`, with a burn-down by directory** starting with
   `src/components` (the message names the on-scale value for most hits). Turn it off for
   `shadcn/components/ui`. Move to `error` once a directory reaches zero.
6. **`no-restyle` last, as `warn`.** 861 in app code and policy-heavy: tune the contracts per
   component first (for example allow layout classes on `Button`), because the defaults
   describe a stricter system than this one. `src/views/organism` alone holds about a third of the findings.

To track a burn-down, re-run the command in "How the baseline was produced" and compare the
per-rule totals; the count of findings per rule is the metric.
