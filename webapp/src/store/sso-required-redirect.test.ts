import { configureStore, createAction } from '@reduxjs/toolkit';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { isDashboardPath, isSsoRequiredError, navigation, resetSsoRedirect, ssoRequiredRedirect } from './sso-required-redirect';

const rejected = (payload: unknown) => ({ type: 'someApi/executeQuery/rejected', payload, meta: { requestId: 'r1', rejectedWithValue: true, requestStatus: 'rejected' }, error: { message: 'Rejected' } });
const ssoRefusal = { status: 403, data: { code: 'sso_required', message: 'Your organisation requires single sign-on' } };

describe('ssoRequiredRedirect', () => {
    const assign = vi.fn();

    const at = (pathname: string) => window.history.pushState({}, '', pathname);
    const dispatch = (action: unknown) => {
        const store = configureStore({ reducer: (state = {}) => state, middleware: (getDefault) => getDefault().concat(ssoRequiredRedirect) });
        return store.dispatch(action as any);
    };

    beforeEach(() => {
        assign.mockReset();
        resetSsoRedirect();
        vi.spyOn(navigation, 'goTo').mockImplementation(assign);
    });
    afterEach(() => {
        vi.restoreAllMocks();
        window.history.pushState({}, '', '/');
    });

    it('sends a dashboard page to the selection with the single sign-on notice', () => {
        at('/acme/dashboard/forms');
        dispatch(rejected(ssoRefusal));
        expect(assign).toHaveBeenCalledWith('/workspace/select?notice=sso_required');
    });

    it('navigates once when several requests are refused together', () => {
        at('/acme/dashboard/forms');
        dispatch(rejected(ssoRefusal));
        dispatch(rejected(ssoRefusal));
        dispatch(rejected(ssoRefusal));
        expect(assign).toHaveBeenCalledTimes(1);
    });

    it('also from the onboarding', () => {
        at('/acme/onboarding');
        dispatch(rejected(ssoRefusal));
        expect(assign).toHaveBeenCalledTimes(1);
    });

    it('leaves the selection screen and public pages alone', () => {
        for (const path of ['/workspace/select', '/acme/forms/f1', '/acme', '/login']) {
            at(path);
            dispatch(rejected(ssoRefusal));
        }
        expect(assign).not.toHaveBeenCalled();
    });

    it('ignores every other failure, and an action that is not a rejection', () => {
        at('/acme/dashboard/forms');
        dispatch(rejected({ status: 403, data: 'Forbidden' }));
        dispatch(rejected({ status: 403, data: { code: 'respondent_session' } }));
        dispatch(rejected({ status: 401, data: { code: 'sso_required' } }));
        dispatch(rejected({ status: 500 }));
        dispatch(createAction('plain')());
        expect(assign).not.toHaveBeenCalled();
    });

    it('recognises only the 403 with the code', () => {
        expect(isSsoRequiredError(ssoRefusal)).toBe(true);
        expect(isSsoRequiredError(undefined)).toBe(false);
        expect(isSsoRequiredError({ status: 403, data: null })).toBe(false);
    });

    it('knows the dashboard paths', () => {
        expect(isDashboardPath('/acme/dashboard')).toBe(true);
        expect(isDashboardPath('/acme/dashboard/forms/x')).toBe(true);
        expect(isDashboardPath('/acme/dashboardx')).toBe(false);
    });
});
