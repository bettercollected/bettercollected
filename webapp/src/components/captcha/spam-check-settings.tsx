'use client';

import { useTranslation } from 'react-i18next';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Switch } from '@app/shadcn/components/ui/switch';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAppSelector } from '@app/store/hooks';
import { CaptchaCounts, useGetCaptchaSettingsQuery, useGetWorkspaceCaptchaCountsQuery, useSetCaptchaDefaultMutation } from '@app/store/workspaces/captcha-api';
import { selectWorkspace } from '@app/store/workspaces/slice';

/** The counts of a form or workspace, in one sentence per purpose (numbers only). */
export function CaptchaCountsLines({ counts, testId }: { counts?: CaptchaCounts; testId?: string }) {
    const { t } = useTranslation();
    if (!counts) return null;
    return (
        <ul className="text-black-700 flex flex-col gap-0.5 text-xs" data-testid={testId}>
            <li>{t('STAFF.SPAM_CHECK.COUNTS_SUBMIT', { days: counts.days, passed: counts.submit.passed, blocked: counts.submit.blocked })}</li>
            <li>{t('STAFF.SPAM_CHECK.COUNTS_MAIL', { days: counts.days, passed: counts.mail.passed, blocked: counts.mail.blocked })}</li>
        </ul>
    );
}

/**
 * Workspace settings, "Spam protection": whether the workspace's forms ask for the automatic spam check
 * unless a form says otherwise (docs/captcha.md), and what the check did in the last 30 days (counts only).
 * Owners and admins (workspace.manage) only, and only while this server has the check on; the sidebar item
 * is hidden under the same two conditions. A change is saved at once.
 */
export default function SpamCheckSettings() {
    const { t } = useTranslation();
    const { can, ready, captchaEnabled } = useWorkspacePermissions();

    if (!ready) return <div className="text-black-600 px-5 py-6 text-sm lg:px-10">{t('STAFF.SPAM_CHECK.LOADING')}</div>;
    if (!can(WorkspacePermission.WORKSPACE_MANAGE)) return <p className="text-black-700 px-5 py-6 text-sm lg:px-10">{t('STAFF.SPAM_CHECK.ONLY_ADMINS')}</p>;
    if (!captchaEnabled) return <p className="text-black-700 px-5 py-6 text-sm lg:px-10">{t('STAFF.SPAM_CHECK.TURNED_OFF')}</p>;
    return <Default />;
}

function Default() {
    const { t } = useTranslation();
    const { toast } = useToast();
    const workspace = useAppSelector(selectWorkspace);
    const settings = useGetCaptchaSettingsQuery(workspace?.id as string, { skip: !workspace?.id });
    const counts = useGetWorkspaceCaptchaCountsQuery(workspace?.id as string, { skip: !workspace?.id, refetchOnMountOrArgChange: true });
    const [save, { isLoading: saving }] = useSetCaptchaDefaultMutation();

    const change = async (captchaDefault: boolean) => {
        const response = await save({ workspaceId: workspace.id as string, captchaDefault });
        if ('error' in response && response.error) toast({ description: t('STAFF.SPAM_CHECK.SAVE_FAILED'), variant: 'destructive' });
        else toast({ description: t(captchaDefault ? 'STAFF.SPAM_CHECK.SAVED_ON' : 'STAFF.SPAM_CHECK.SAVED_OFF') });
    };

    return (
        <div className="flex w-full max-w-[720px] flex-col gap-8 px-5 py-6 lg:px-10">
            <p className="text-black-600 max-w-[62ch] text-sm leading-relaxed">{t('STAFF.SPAM_CHECK.PAGE_INTRO')}</p>

            <section aria-labelledby="spam-default" className="flex flex-col gap-3">
                {settings.isLoading ? (
                    <p role="status" className="text-black-600 text-sm">
                        {t('STAFF.SPAM_CHECK.LOADING')}
                    </p>
                ) : settings.isError ? (
                    <p role="alert" className="text-sm text-[#C43D3D]">
                        {t('STAFF.SPAM_CHECK.LOAD_FAILED')}
                    </p>
                ) : (
                    <div className="border-black-300 flex items-start justify-between gap-6 rounded border bg-white p-4">
                        <div className="flex max-w-[520px] flex-col gap-1">
                            <h2 id="spam-default" className="text-black-900 text-[15px] font-semibold">
                                {t('STAFF.SPAM_CHECK.DEFAULT_TITLE')}
                            </h2>
                            <p id="spam-default-description" className="text-black-700 text-sm leading-relaxed">
                                {t('STAFF.SPAM_CHECK.DEFAULT_DESCRIPTION')}
                            </p>
                        </div>
                        <Switch data-testid="spam-default-switch" aria-labelledby="spam-default" aria-describedby="spam-default-description" checked={settings.data?.captchaDefault !== false} disabled={saving || !settings.data?.canManage} onCheckedChange={change} />
                    </div>
                )}
            </section>

            <section aria-labelledby="spam-counts" className="flex flex-col gap-2">
                <h2 id="spam-counts" className="text-black-900 text-base font-semibold">
                    {t('STAFF.SPAM_CHECK.COUNTS_TITLE')}
                </h2>
                {counts.isError ? (
                    <p role="alert" className="text-sm text-[#C43D3D]">
                        {t('STAFF.SPAM_CHECK.LOAD_FAILED')}
                    </p>
                ) : (
                    <CaptchaCountsLines counts={counts.data} testId="spam-counts" />
                )}
                <p className="text-black-600 text-xs leading-relaxed">{t('STAFF.SPAM_CHECK.COUNTS_NOTE')}</p>
            </section>
        </div>
    );
}
