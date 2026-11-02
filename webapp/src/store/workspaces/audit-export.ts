import environments from '@app/configs/environments';
import { pathSegment } from '@app/store/workspaces/api';

// Taking the audit log out as a file (backend controllers/audit_log_export_router.py, docs/audit-log.md): the file of
// the filters on screen, CSV or JSON. The answer is a file, not JSON, so it is fetched here and handed to the browser
// as a download (a fetch, which the server requires: a followed link is refused); a refusal carries a `code` the dialog words in the reader's language.

export type AuditExportFormat = 'csv' | 'json';

export type AuditExportResult = { ok: true; fileName: string; blob: Blob } | { ok: false; code: string };

const fileNameOf = (disposition: string | null, format: AuditExportFormat): string => {
    const match = /filename="([^"\\;]+)"/.exec(disposition ?? '');
    const name = match?.[1];
    // only a plain file name is used: never a path, whatever the header says
    return name && /^[A-Za-z0-9._-]{1,80}$/.test(name) ? name : `audit-log.${format}`;
};

/**
 * Asks the server for the file of `query` (the same query string as the list, without a cursor or a limit). The
 * server records the export before it sends a byte, so a failure to record is a refusal here too (`audit_unavailable`).
 */
export async function requestAuditExport({ workspaceId, formId, query, format }: { workspaceId: string; formId?: string; query: string; format: AuditExportFormat }): Promise<AuditExportResult> {
    const search = new URLSearchParams(query);
    search.set('format', format);
    const path = `/workspaces/${pathSegment(workspaceId)}${formId ? `/forms/${pathSegment(formId)}` : ''}/audit-log/export?${search.toString()}`;
    try {
        const response = await fetch(`${environments.API_ENDPOINT_HOST}${path}`, { method: 'GET', mode: 'cors', credentials: 'include' });
        if (!response.ok) {
            let code = `http_${response.status}`;
            try {
                const body = await response.json();
                if (typeof body?.code === 'string') code = body.code;
                else if (typeof body?.detail?.code === 'string') code = body.detail.code;
            } catch {
                // an error without a body: the status says enough
            }
            return { ok: false, code };
        }
        return { ok: true, fileName: fileNameOf(response.headers.get('Content-Disposition'), format), blob: await response.blob() };
    } catch {
        return { ok: false, code: 'network' };
    }
}

/** Hands a blob to the browser as a download (an object URL, released at once). */
export function saveBlob(fileName: string, blob: Blob): void {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}
