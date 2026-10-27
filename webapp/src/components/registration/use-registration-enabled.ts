import { useAppSelector } from '@app/store/hooks';
import { useGetRegistrationStatusQuery } from '@app/store/workspaces/registration-api';
import { selectWorkspace } from '@app/store/workspaces/slice';

/**
 * Whether this server sends submissions to case systems
 * (`GET /workspaces/{id}/registration/status`). Every registration screen is
 * hidden while it is false, and while the answer has not arrived.
 */
export function useRegistrationEnabled() {
    const workspace = useAppSelector(selectWorkspace);
    const { data, isLoading } = useGetRegistrationStatusQuery(workspace?.id as string, { skip: !workspace?.id });
    return { enabled: data?.enabled === true, isLoading };
}
