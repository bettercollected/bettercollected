import { useAppSelector } from '@app/store/hooks';
import { useGetWebhooksStatusQuery } from '@app/store/workspaces/webhooks-api';
import { selectWorkspace } from '@app/store/workspaces/slice';

/**
 * Whether this server has webhooks on (`GET /workspaces/{id}/webhooks/status`).
 * Every webhook screen is hidden while it is false, and while the answer has
 * not arrived.
 */
export function useWebhooksEnabled() {
    const workspace = useAppSelector(selectWorkspace);
    const { data, isLoading } = useGetWebhooksStatusQuery(workspace?.id as string, { skip: !workspace?.id });
    return { enabled: data?.enabled === true, isLoading };
}
