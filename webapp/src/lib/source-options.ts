import environments from '@app/configs/environments';
import type { SourceOption, SourceOptionsPage } from '@app/utils/option-sources';

export interface SourceOptionsRequest {
    workspaceId: string;
    formId: string;
    fieldId: string;
    q?: string;
    offset?: number;
    limit?: number;
    /** The ids chosen in the question a dependent list depends on. */
    parent?: string[];
}

/**
 * One page of the choices of a question whose options come from a list or from another form's answers, through our
 * server (a public route, like the form; labels only). A plain request, not a store endpoint: the store would keep
 * the typed search text as the request's argument (and in the browser's Redux DevTools history), and the labels may
 * be other people's answers; here they live only in the component.
 *
 * Rejects (with no detail of the reply) for every failure: the caller says the choices cannot be loaded.
 */
export async function fetchSourceOptions({ workspaceId, formId, fieldId, q, offset = 0, limit = 50, parent = [] }: SourceOptionsRequest, signal?: AbortSignal): Promise<SourceOptionsPage> {
    const params = new URLSearchParams();
    if (q) params.set('q', q.slice(0, 100));
    params.set('offset', String(offset));
    params.set('limit', String(limit));
    parent.slice(0, 50).forEach((id) => params.append('parent', id));
    const response = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${encodeURIComponent(workspaceId)}/forms/${encodeURIComponent(formId)}/options/${encodeURIComponent(fieldId)}?${params}`, {
        credentials: 'include',
        cache: 'no-store',
        signal
    });
    if (!response.ok) throw new Error('options unavailable');
    return pageOf(await response.json());
}

/** A reply read defensively: ids and texts only. */
export function pageOf(data: unknown): SourceOptionsPage {
    const reply = data as { items?: unknown; total?: unknown; truncated?: unknown; available?: unknown } | null;
    if (!reply || !Array.isArray(reply.items)) throw new Error('options unavailable');
    const items: SourceOption[] = reply.items.filter((item: any) => item && typeof item.id === 'string' && typeof item.label === 'string').map((item: any) => ({ id: item.id, label: item.label }));
    return { items, total: typeof reply.total === 'number' ? reply.total : items.length, truncated: reply.truncated === true, available: reply.available !== false };
}
