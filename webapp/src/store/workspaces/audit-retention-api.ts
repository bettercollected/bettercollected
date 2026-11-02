import { AuditRetentionDto } from '@app/models/dtos/audit-log-dto';
import { pathSegment, workspacesApi } from '@app/store/workspaces/api';

// How long the workspace keeps its audit entries (backend controllers/audit_log_router.py, docs/audit-log.md). Reading
// needs audit.read, changing it is for owners only; both answer 422 `audit_log_off` while the server's
// AUDIT_LOG_UI_ENABLED is off (the webapp asks for neither then). A change answers the new setting, which replaces
// the cached one.

export const auditRetentionApi = workspacesApi.injectEndpoints({
    endpoints: (builder) => ({
        getAuditRetention: builder.query<AuditRetentionDto, string>({
            query: (workspaceId) => ({ url: `/workspaces/${pathSegment(workspaceId)}/audit-log/retention`, method: 'GET' })
        }),
        setAuditRetention: builder.mutation<AuditRetentionDto, { workspaceId: string; months: number }>({
            query: ({ workspaceId, months }) => ({ url: `/workspaces/${pathSegment(workspaceId)}/audit-log/retention`, method: 'PUT', body: { months } }),
            async onQueryStarted({ workspaceId }, { dispatch, queryFulfilled }) {
                try {
                    const { data } = await queryFulfilled;
                    dispatch(auditRetentionApi.util.updateQueryData('getAuditRetention', workspaceId, () => data));
                } catch {
                    // the dialog shows the refusal; the cached figure stays as it was
                }
            }
        })
    })
});

export const { useGetAuditRetentionQuery, useSetAuditRetentionMutation } = auditRetentionApi;
