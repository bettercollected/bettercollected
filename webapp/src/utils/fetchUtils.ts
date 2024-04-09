import { cookies } from 'next/headers';
import { notFound } from 'next/navigation';

export default async function fetchWithCookies(
    input: string | URL | globalThis.Request,
    init?: RequestInit
) {
    const cookieStore = cookies();
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

    const response = await fetch(input, config);
    const contentType = response.headers.get('content-type');

    if (contentType?.includes('application/json')) {
        return await response.json();
    } else if (contentType?.includes('text/html')) {
        return await response.text();
    } else {
        return response;
    }
}
