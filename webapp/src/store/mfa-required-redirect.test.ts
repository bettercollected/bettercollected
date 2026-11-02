import { configureStore } from '@reduxjs/toolkit';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { isMfaRequiredError, mfaNavigation, mfaRequiredRedirect, mfaVerifyUrl, resetMfaRedirect } from './mfa-required-redirect';

const rejected = (payload: unknown) => ({ type: 'someApi/executeQuery/rejected', payload, meta: { requestId: 'r1', rejectedWithValue: true, requestStatus: 'rejected' }, error: { message: 'Rejected' } });
const refusal = { status: 403, data: { code: 'mfa_required', message: 'This workspace requires a second factor' } };

describe('mfaRequiredRedirect', () => {
    const goTo = vi.fn();
    const at = (pathname: string) => window.history.pushState({}, '', pathname);
    const dispatch = (action: unknown) => configureStore({ reducer: (state = {}) => state, middleware: (getDefault) => getDefault().concat(mfaRequiredRedirect) }).dispatch(action as any);

    beforeEach(() => {
        goTo.mockReset();
        resetMfaRedirect();
        vi.spyOn(mfaNavigation, 'goTo').mockImplementation(goTo);
    });
    afterEach(() => {
        vi.restoreAllMocks();
        window.history.pushState({}, '', '/');
    });

    it('sends a dashboard page to the verify page of its workspace, remembering where it was', () => {
        at('/acme/dashboard/forms?x=1');
        dispatch(rejected(refusal));
        expect(goTo).toHaveBeenCalledWith('/acme/security/verify?next=%2Facme%2Fdashboard%2Fforms%3Fx%3D1');
    });

    it('navigates once for several refused requests', () => {
        at('/acme/dashboard');
        dispatch(rejected(refusal));
        dispatch(rejected(refusal));
        expect(goTo).toHaveBeenCalledTimes(1);
    });

    it('leaves the verify page itself, other pages and other refusals alone', () => {
        at('/acme/security/verify');
        dispatch(rejected(refusal));
        at('/');
        dispatch(rejected(refusal));
        at('/acme/dashboard');
        dispatch(rejected({ status: 403, data: { code: 'sso_required' } }));
        dispatch(rejected({ status: 500, data: { code: 'mfa_required' } }));
        expect(goTo).not.toHaveBeenCalled();
    });

    it('reads only the exact refusal', () => {
        expect(isMfaRequiredError(refusal)).toBe(true);
        expect(isMfaRequiredError({ status: 403, data: 'mfa_required' })).toBe(false);
        expect(isMfaRequiredError(undefined)).toBe(false);
        expect(mfaVerifyUrl('/acme/dashboard/x')).toBe('/acme/security/verify');
        expect(mfaVerifyUrl('/workspace/select')).toBeNull();
    });
});
