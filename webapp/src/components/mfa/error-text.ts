import type { TFunction } from 'i18next';

import { MfaFailure, waitMinutes } from '@app/utils/mfa';

/**
 * What to tell the user when a second-factor request was refused. One wrong
 * code is always the same message (the server never says why a code failed).
 * `clockHint` adds the advice to check the phone's clock, for the first code.
 */
export function mfaErrorText(t: TFunction, failure: MfaFailure, clockHint = false): string {
    switch (failure.code) {
        case 'invalid_code':
            return t(clockHint ? 'STAFF.MFA.ERRORS.INVALID_CLOCK' : 'STAFF.MFA.ERRORS.INVALID');
        case 'mfa_locked':
        case 'too_many_attempts': {
            // repeated locks last an hour, six hours, a day: say it in hours
            const minutes = waitMinutes(failure.retryAfter);
            return minutes > 90 ? t('STAFF.MFA.ERRORS.LOCKED_HOURS', { count: Math.ceil(minutes / 60) }) : t('STAFF.MFA.ERRORS.LOCKED', { count: minutes });
        }
        case 'mfa_challenge_expired':
            return t('STAFF.MFA.ERRORS.EXPIRED');
        case 'recent_proof_required':
            return t('STAFF.MFA.ERRORS.STALE');
        case 'totp_off':
            return t('STAFF.MFA.ERRORS.OFF');
        case 'required_by_workspace':
            return t('STAFF.MFA.ERRORS.REQUIRED_BY_WORKSPACE');
        case 'no_factor':
            return t('STAFF.MFA.ERRORS.NO_FACTOR');
        default:
            return t('STAFF.MFA.ERRORS.GENERIC');
    }
}
