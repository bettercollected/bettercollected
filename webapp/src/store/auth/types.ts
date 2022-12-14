export const AUTH_TAG_TYPES = 'AUTH_API';
export const AUTH_LOG_OUT = 'AUTH_LOG_OUT';
export const AUTH_OTP_TAGS = 'AUTH_OTP_TAGS';

export interface VerifyOtp {
    email: string;
    otp_code: string;
}
