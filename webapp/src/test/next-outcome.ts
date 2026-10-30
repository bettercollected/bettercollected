import { isRedirectError } from 'next/dist/client/components/redirect-error';

/**
 * What a server component or check did: `{ redirect: url }` for `redirect()`,
 * `{ notFound: true }` for `notFound()`, else `{ value }`. For tests of
 * server pages and layouts called as plain functions.
 */
export async function nextOutcome<T>(run: () => Promise<T>): Promise<{ redirect?: string; notFound?: boolean; value?: T }> {
    try {
        return { value: await run() };
    } catch (error) {
        // digest: NEXT_REDIRECT;<type>;<url>;<status>;
        if (isRedirectError(error)) return { redirect: error.digest.split(';').slice(2, -2).join(';') };
        const digest = (error as { digest?: unknown })?.digest;
        if (typeof digest === 'string' && digest.startsWith('NEXT_HTTP_ERROR_FALLBACK;404')) return { notFound: true };
        throw error;
    }
}

/**
 * A `fetch` stand-in answering by URL: the first route whose pattern the URL
 * contains answers (a fresh Response each call); anything else is a 404.
 * The URLs asked are kept in `asked`.
 */
export function fakeApi(routes: Array<[string, number, unknown]>) {
    const asked: string[] = [];
    const fetch = async (input: unknown) => {
        const url = String(input);
        asked.push(url);
        const route = routes.find(([pattern]) => url.includes(pattern));
        if (!route) return new Response('{}', { status: 404 });
        return new Response(JSON.stringify(route[2]), { status: route[1] });
    };
    return { fetch, asked };
}
