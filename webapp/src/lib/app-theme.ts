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
