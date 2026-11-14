'use client';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { useGetFormCaptchaCountsQuery } from '@app/store/workspaces/captcha-api';

import { CaptchaCountsLines } from './spam-check-settings';

/**
 * What the spam check did for one form in the last 30 days, under its setting: numbers only
 * (proofs that passed, proofs refused), for those who may read analytics. Asked only while
 * this server has the check on (the row is not shown otherwise).
 */
export default function FormCaptchaCounts({ workspaceId, formId }: { workspaceId?: string; formId?: string }) {
    const { can } = useWorkspacePermissions();
    const allowed = !!workspaceId && !!formId && can(WorkspacePermission.ANALYTICS_READ);
    const { data } = useGetFormCaptchaCountsQuery({ workspaceId: workspaceId as string, formId: formId as string }, { skip: !allowed, refetchOnMountOrArgChange: true });
    return allowed ? <CaptchaCountsLines counts={data} testId="form-captcha-counts" /> : null;
}
