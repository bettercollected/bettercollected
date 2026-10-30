import { formsApi } from '@app/store/redux/form-api';
import { workspacesApi } from '@app/store/workspaces/api';
import { forgetResponseList } from '@app/utils/response-list-memory';

/**
 * Forget what the signed-out user saw, so the next person at this browser
 * does not get it back (on the page Back returns to, or from a cache): the
 * cached workspaces, forms, responses and permissions, and the responses list
 * memory (whose search may be a responder's email).
 *
 * The one reset for every way out: the logout dialog, the invitation page's
 * "switch account", and the server saying that nobody (or someone else) is
 * signed in any more (AuthDispatcher).
 */
export function resetAfterSignOut(dispatch: (action: any) => unknown) {
    dispatch(workspacesApi.util.resetApiState());
    dispatch(formsApi.util.resetApiState());
    forgetResponseList();
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
