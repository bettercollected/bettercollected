/**
 * The look of the staff dashboard: a workspace setting with two values, chosen by its owners and admins
 * (`PUT /workspaces/{id}/app-theme`, backend docs/app-theme.md). `daybreak` is the default. The server sends the value
 * with the workspace to members only (never to a respondent), and `daybreak` whatever is stored while its Pigment
 * switch is off.
 */
export const APP_THEMES = ['daybreak', 'pigment'] as const;

export type AppTheme = (typeof APP_THEMES)[number];

export const DEFAULT_APP_THEME: AppTheme = 'daybreak';

/** `value` as one of the two themes, `daybreak` for anything else (a missing value, a value a newer server sends). */
export function asAppTheme(value: unknown): AppTheme {
    return value === 'pigment' ? 'pigment' : DEFAULT_APP_THEME;
}

/**
 * The app roles a respondent's form must not inherit. A form drawn inside an app theme scope (the builder canvas, the
 * preview page, the preview dialog of a Pigment workspace) would otherwise read the theme's colours where the real
 * respondent page, which has no scope, reads the frozen blue. Each is a role whose utility or rule falls back to the
 * frozen value, `var(--app-x, <frozen>)`: the form root sets it to `initial`, so the fallback applies again
 * (`formRootProps` in views/molecules/theme/theme-root.ts). One entry per line; `app-theme.test.ts` fails when a role
 * that is read with a fallback is missing here, or an entry names a role no theme block declares.
 */
// prettier-ignore
export const APP_ROLES_RESET_ON_FORMS = [
    '--app-action',
    '--app-action-hover',
    '--app-action-pressed',
    '--app-on-action',
    '--app-focus-ring',
    '--app-primary',
    '--app-primary-deep',
    '--app-primary-soft',
    '--app-primary-tint',
    '--app-edge',
    '--app-edge-strong',
    '--app-wash',
    '--app-wash-strong',
    '--app-control'
] as const;
