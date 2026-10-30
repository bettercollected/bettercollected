import { UserStatus } from '@app/models/dtos/user-status';

/**
 * Only an explicit 401 from `/auth/status` means the session has ended (the
 * backend refreshes an expired access token itself and answers 401 once
 * the session cannot be refreshed). A server error (502/503 during a deploy,
 * 429), a timeout or a network failure (laptop wake, Wi-Fi drop) says nothing
 * about the session: the user stays signed in, with their caches, and the
 * status check simply asks again.
 */

/**
 * Whether a failed `/auth/status` request (an RTK Query `fetchBaseQuery`
 * error) is the server saying that nobody is signed in: `{ status: 401 }`,
 * or a 401 whose body was not JSON (`PARSING_ERROR` with `originalStatus`
 * 401). `FETCH_ERROR`, `TIMEOUT_ERROR` and every other status are not.
 */
export function isSignedOutError(error: unknown): boolean {
    if (!error || typeof error !== 'object') return false;
    const { status, originalStatus } = error as { status?: unknown; originalStatus?: unknown };
    return status === 401 || (status === 'PARSING_ERROR' && originalStatus === 401);
}

/** What the server-side `/auth/status` request said. */
export type ServerAuthAnswer =
    // a user is signed in
    | { kind: 'signed-in'; user: UserStatus }
    // the server answered 401: nobody is signed in
    | { kind: 'signed-out' }
    // nothing usable: a 5xx, an HTML error page, the backend out of reach
    | { kind: 'unknown' };

/** Reads the status code and parsed body of the server-side `/auth/status` request. */
export function readServerAuthAnswer(status: number, body: unknown): ServerAuthAnswer {
    if (status === 401) return { kind: 'signed-out' };
    const id = body && typeof body === 'object' ? (body as { id?: unknown }).id : undefined;
    if (status >= 200 && status < 300 && typeof id === 'string' && id) return { kind: 'signed-in', user: body as UserStatus };
    return { kind: 'unknown' };
}
