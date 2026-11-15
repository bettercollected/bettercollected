'use client';

import { useEffect, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { AppThemePreview } from '@app/components/app-theme/app-theme-previews';
import { StatusPill } from '@app/components/ui/status-pill';
import { APP_THEMES, AppTheme, asAppTheme } from '@app/lib/app-theme';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { RadioGroup, RadioGroupItem } from '@app/shadcn/components/ui/radio-group';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { useAppSelector } from '@app/store/hooks';
import { useSetWorkspaceAppThemeMutation } from '@app/store/workspaces/app-theme-api';
import { selectWorkspace } from '@app/store/workspaces/slice';

// The name is a proper noun and is the same in every language; the description is words.
const NAME_KEY: Record<AppTheme, string> = { daybreak: 'STAFF.APP_THEME.DAYBREAK_NAME', pigment: 'STAFF.APP_THEME.PIGMENT_NAME' };
const DESCRIPTION_KEY: Record<AppTheme, string> = { daybreak: 'STAFF.APP_THEME.DAYBREAK_DESCRIPTION', pigment: 'STAFF.APP_THEME.PIGMENT_DESCRIPTION' };

/** Why a save failed, in words: the server's refusals are told apart, anything else is a plain failure. */
export function appThemeErrorKey(error: unknown): string {
    const status = (error as { status?: unknown } | undefined)?.status;
    const code = (error as { data?: { code?: unknown } } | undefined)?.data?.code;
    if (status === 403) return 'STAFF.APP_THEME.FORBIDDEN';
    if (status === 422 && code === 'app_theme_disabled') return 'STAFF.APP_THEME.DISABLED';
    return 'STAFF.APP_THEME.FAILED';
}

/**
 * "Appearance", on the workspace's Themes page: which of the two app themes the dashboard wears for everyone in the
 * workspace. Offered only to a member who may manage the workspace (`workspace.manage`) and only while the server has
 * the Pigment switch on (`appThemeEnabled` of the permissions): otherwise nothing is rendered and nothing is asked
 * of the server. The current theme comes from the workspace in the store, which the server filled in for members.
 * A choice is made with the radio group and kept with Save; the result is written in a status line (read out by a
 * screen reader) and focus never leaves the control that was used.
 */
export default function AppearanceCard() {
    const { can, appThemeEnabled } = useWorkspacePermissions();
    if (!appThemeEnabled || !can(WorkspacePermission.WORKSPACE_MANAGE)) return null;
    return <Appearance />;
}

function Appearance() {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const current = asAppTheme(workspace?.appTheme);
    const [choice, setChoice] = useState<AppTheme>(current);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState('');
    const [errorKey, setErrorKey] = useState('');
    const [save] = useSetWorkspaceAppThemeMutation();

    // the workspace's theme changed elsewhere (another tab's change after a reload, a save of this card)
    useEffect(() => setChoice(current), [current]);

    const name = (theme: AppTheme) => t(NAME_KEY[theme]);
    const unchanged = choice === current;

    const onSave = async () => {
        if (saving) return;
        setErrorKey('');
        if (unchanged) {
            setMessage(t('STAFF.APP_THEME.NO_CHANGE', { name: name(current) }));
            return;
        }
        setMessage('');
        setSaving(true);
        const response = await save({ workspaceId: workspace.id as string, appTheme: choice });
        setSaving(false);
        if ('error' in response && response.error) {
            setErrorKey(appThemeErrorKey(response.error));
            return;
        }
        setMessage(t('STAFF.APP_THEME.SAVED', { name: name(choice) }));
    };

    return (
        <section aria-labelledby="appearance-title" className="flex flex-col gap-4" data-testid="appearance-card">
            <div className="flex flex-col gap-1">
                <h2 id="appearance-title" className="text-ink text-base font-semibold">
                    {t('STAFF.APP_THEME.TITLE')}
                </h2>
                <p id="appearance-hint" className="text-copy max-w-[62ch] text-sm">
                    {t('STAFF.APP_THEME.HINT')}
                </p>
            </div>

            <div className="border-hairline-strong bg-surface flex max-w-[720px] flex-col gap-5 rounded border p-4 sm:p-5">
                <RadioGroup
                    value={choice}
                    onValueChange={(value) => {
                        if (saving) return;
                        setMessage('');
                        setErrorKey('');
                        setChoice(asAppTheme(value));
                    }}
                    aria-labelledby="appearance-title"
                    aria-describedby="appearance-hint"
                    className="grid grid-cols-1 gap-3 sm:grid-cols-2"
                >
                    {APP_THEMES.map((theme) => (
                        <label key={theme} htmlFor={`app-theme-${theme}`} className={cn('flex cursor-pointer flex-col gap-3 rounded border p-3 transition-colors', choice === theme ? 'option-selected' : 'border-hairline-strong hover:bg-sunken')}>
                            <AppThemePreview theme={theme} className="border-hairline w-full rounded border" />
                            <span className="flex items-start gap-2.5">
                                <RadioGroupItem id={`app-theme-${theme}`} value={theme} aria-labelledby={`app-theme-${theme}-name`} aria-describedby={`app-theme-${theme}-description`} className="mt-0.5 shrink-0" />
                                <span className="flex min-w-0 flex-col gap-0.5">
                                    <span className="flex flex-wrap items-center gap-2">
                                        <span id={`app-theme-${theme}-name`} className="text-ink text-sm font-semibold">
                                            {name(theme)}
                                        </span>
                                        {current === theme && <StatusPill tone="info">{t('STAFF.APP_THEME.IN_USE')}</StatusPill>}
                                    </span>
                                    <span id={`app-theme-${theme}-description`} className="text-copy text-sm leading-snug">
                                        {t(DESCRIPTION_KEY[theme])}
                                    </span>
                                </span>
                            </span>
                        </label>
                    ))}
                </RadioGroup>

                <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                    <Button
                        type="button"
                        size="sm"
                        variant="primary"
                        busy={saving}
                        aria-disabled={unchanged || saving ? true : undefined}
                        onClick={onSave}
                        className="aria-disabled:bg-black-300 aria-disabled:text-black-600 aria-disabled:hover:bg-black-300 aria-disabled:[--key-edge:var(--color-black-400)] aria-disabled:cursor-not-allowed"
                    >
                        {t('STAFF.APP_THEME.SAVE')}
                    </Button>
                    {/* always in the page, so a screen reader announces the text that arrives in it */}
                    <p role="status" aria-live="polite" className="text-ink-muted text-sm" data-testid="appearance-status">
                        {message}
                    </p>
                </div>
                {errorKey && (
                    <p role="alert" className="text-bad text-sm" data-testid="appearance-error">
                        {t(errorKey)}
                    </p>
                )}
            </div>
        </section>
    );
}
