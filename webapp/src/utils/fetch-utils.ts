import { cookies } from 'next/headers';
import { notFound } from 'next/navigation';

/**
 * A server-side fetch that carries the browser's session cookies. The raw
 * response, for callers that need its status code.
 */
export async function fetchWithCookiesResponse(input: string | URL | globalThis.Request, init?: RequestInit) {
    const cookieStore = await cookies();
    const Authorization = cookieStore.get('Authorization')?.value;
    const RefreshToken = cookieStore.get('RefreshToken')?.value;

    const auth = !!Authorization ? `Authorization=${Authorization}` : '';
    const refresh = !!RefreshToken ? `RefreshToken=${RefreshToken}` : '';

    const config = {
        headers: {
            cookie: `${auth};${refresh}`
        },
        ...(init || {})
    };

    return await fetch(input, config);
}

export default async function fetchWithCookies(
    input: string | URL | globalThis.Request,
    init?: RequestInit
) {
    const response = await fetchWithCookiesResponse(input, init);
    const contentType = response.headers.get('content-type');

    if (contentType?.includes('application/json')) {
        return await response.json();
    } else if (contentType?.includes('text/html')) {
        return await response.text();
    } else {
        return response;
    }
}
