import { useAppSelector } from '@app/store/hooks';
import { useGetEmailActionsStatusQuery } from '@app/store/workspaces/email-actions-api';
import { selectWorkspace } from '@app/store/workspaces/slice';

/**
 * Whether this server has email actions on, and a mail server
 * (`GET /workspaces/{id}/email-actions/status`). Every email screen is hidden
 * while `enabled` is false, and while the answer has not arrived.
 */
export function useEmailActionsStatus() {
    const workspace = useAppSelector(selectWorkspace);
    const { data, isLoading } = useGetEmailActionsStatusQuery(workspace?.id as string, { skip: !workspace?.id });
    return { enabled: data?.enabled === true, configured: data?.configured === true, isLoading };
}
