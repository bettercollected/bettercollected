import { API_SLICES } from '@app/store/api-slices';
import { authApi } from '@app/store/auth/api';
import { forgetLastWorkspace } from '@app/lib/workspace-selection';
import { resetSingleForm } from '@app/store/forms/slice';
import { forgetResponseList } from '@app/utils/response-list-memory';

/**
 * Forget what the signed-out user saw, so the next person at this browser
 * does not get it back (on the page Back returns to, or from a cache): every
 * RTK Query cache (workspaces, forms, responses, permissions, members and
 * invitations, analytics, imports, …), the form last opened, the
 * responses list memory (whose search may be a responder's email) and the
 * last-used workspace id of the selection screen. Only
 * `authApi` stays: it reads who is signed in now.
 *
 * The one reset for every way out: the logout dialog, the invitation page's
 * "switch account", and the server saying that nobody (or someone else) is
 * signed in any more (AuthDispatcher, AuthStatusDispatcher). "Nobody" means
 * an explicit 401 (utils/session-answer); a server error or a network failure
 * says nothing about the session and resets nothing.
 */
export function resetAfterSignOut(dispatch: (action: any) => unknown) {
    for (const api of API_SLICES) {
        if (api.reducerPath !== authApi.reducerPath) dispatch(api.util.resetApiState());
    }
    dispatch(resetSingleForm());
    forgetResponseList();
    forgetLastWorkspace();
}

/**
 * The same reset, when the server reports who is signed in now: only when
 * this browser still holds another user's data (a user was signed in here
 * and now nobody, or someone else, is). A first load has nothing to forget,
 * and an anonymous visitor's queries are left alone.
 */
export const resetIfUserChanged =
    (nextUserId: string | undefined | null) =>
    (dispatch: (action: any) => unknown, getState: () => { auth?: { id?: string } }) => {
        const before = getState().auth?.id;
        if (before && before !== (nextUserId || undefined)) resetAfterSignOut(dispatch);
    };
