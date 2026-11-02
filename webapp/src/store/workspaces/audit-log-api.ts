import { AuditPageDto } from '@app/models/dtos/audit-log-dto';
import { pathSegment, workspacesApi } from '@app/store/workspaces/api';

// The audit log (backend controllers/audit_log_router.py, docs/audit-log.md): the workspace's entries and one form's,
// newest first, a keyset page at a time. Both answer 422 `audit_log_off` while the server's AUDIT_LOG_UI_ENABLED is
// off, and 403 without audit.read; the webapp asks for neither then (`useWorkspacePermissions().auditLogUiEnabled`).
// `query` is the finished query string (the filters repeat `area` and `event`, which a params object cannot).

export const auditLogApi = workspacesApi.injectEndpoints({
    endpoints: (builder) => ({
        getAuditLog: builder.query<AuditPageDto, { workspaceId: string; formId?: string; query: string }>({
            query: ({ workspaceId, formId, query }) => ({
                url: `/workspaces/${pathSegment(workspaceId)}${formId ? `/forms/${pathSegment(formId)}` : ''}/audit-log${query ? `?${query}` : ''}`,
                method: 'GET'
            })
        })
    })
});

export const { useLazyGetAuditLogQuery } = auditLogApi;
