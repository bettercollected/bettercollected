import environments from '@app/configs/environments';

export type AddressLookupResult = { status: 'found'; street: string; city: string } | { status: 'not_found' };

export interface AddressLookupRequest {
    workspaceId: string;
    formId: string;
    fieldId: string;
    postcode: string;
    houseNumber: string;
}

/**
 * Street and city of a Dutch postcode and house number, through our server (a public route, like the form; the
 * addition is never sent). A plain request, not a store endpoint: the store would keep the postcode and house
 * number as the request's argument (and in the browser's Redux DevTools history); here they live only in this call.
 *
 * Rejects (with no detail of the reply) for every failure: the caller offers typing instead.
 */
export async function lookUpAddress({ workspaceId, formId, fieldId, postcode, houseNumber }: AddressLookupRequest, signal?: AbortSignal): Promise<AddressLookupResult> {
    const response = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${encodeURIComponent(workspaceId)}/forms/${encodeURIComponent(formId)}/address-lookup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fieldId, postcode, houseNumber }),
        credentials: 'include',
        cache: 'no-store',
        signal
    });
    if (!response.ok) throw new Error('address lookup unavailable');
    const data: unknown = await response.json();
    const reply = data as { status?: unknown; street?: unknown; city?: unknown } | null;
    if (reply?.status === 'not_found') return { status: 'not_found' };
    if (reply?.status === 'found' && typeof reply.street === 'string' && typeof reply.city === 'string') return { status: 'found', street: reply.street, city: reply.city };
    throw new Error('address lookup unavailable');
}
