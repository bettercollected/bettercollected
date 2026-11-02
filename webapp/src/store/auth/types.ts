export const AUTH_TAG_TYPES = 'AUTH_API';

export const AUTH_REFRESH_TAG = 'AUTH_REFRESH_TAG';
export const AUTH_LOG_OUT = 'AUTH_LOG_OUT';
export const AUTH_OTP_TAGS = 'AUTH_OTP_TAGS';
export const AUTH_SESSIONS_TAG = 'AUTH_SESSIONS_TAG';
export const AUTH_MFA_TAG = 'AUTH_MFA_TAG';

/** One of the signed-in user's sessions (GET /auth/sessions). */
export interface AuthSession {
    id: string;
    createdAt?: string;
    lastRefreshedAt?: string;
    expiresAt?: string;
    userAgent?: string;
    // "sso" for a single sign-on session
    method?: string | null;
    current: boolean;
}

export interface VerifyOtp {
    body: {
        email: string;
        otp_code: string;
    };
    params: {
        prospective_pro_user?: boolean;
        workspace_id?: string;
    };
}

/** GET /auth/mfa/status: `available` is the server's TOTP_ENABLED switch. */
export interface MfaStatus {
    available: boolean;
    enabled: boolean;
    recoveryLeft?: number | null;
}

/** POST /auth/mfa/totp/enrol: what an authenticator app needs. Shown once; never kept. */
export interface TotpEnrolment {
    factorId: string;
    // the key grouped in fours, for typing in
    secret: string;
    // the otpauth:// address the QR code is drawn from here
    uri: string;
}

/** The answer of a sign-in step that still needs the second factor. */
export interface MfaRequired {
    mfaRequired: true;
}
