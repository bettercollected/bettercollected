import { workspacesApi } from '@app/store/workspaces/api';

// The automatic spam check as a workspace setting and its counts (backend services/captcha/settings.py,
// docs/captcha.md). The server answers 404 `captcha_off` while CAPTCHA_ENABLED is off; the pages are
// only offered while `captchaEnabled` of the workspace permissions is true.

/** The workspace's default: whether its forms ask for the check unless a form says otherwise. */
export interface CaptchaSettings {
    captchaDefault: boolean;
    canManage: boolean;
}

/** Counts of the last `days` days, by purpose: proofs that passed and proofs refused. Numbers only, never a person. */
export interface CaptchaCounts {
    days: number;
    submit: { passed: number; blocked: number };
    mail: { passed: number; blocked: number };
}

const CAPTCHA_SETTINGS_TAG = 'CAPTCHA_SETTINGS_TAG';

export const captchaApi = workspacesApi.enhanceEndpoints({ addTagTypes: [CAPTCHA_SETTINGS_TAG] }).injectEndpoints({
    endpoints: (builder) => ({
        getCaptchaSettings: builder.query<CaptchaSettings, string>({
            query: (workspaceId) => ({ url: `/workspaces/${workspaceId}/captcha/settings`, method: 'GET' }),
            providesTags: [CAPTCHA_SETTINGS_TAG]
        }),
        setCaptchaDefault: builder.mutation<CaptchaSettings, { workspaceId: string; captchaDefault: boolean }>({
            query: ({ workspaceId, captchaDefault }) => ({ url: `/workspaces/${workspaceId}/captcha/settings`, method: 'PUT', body: { captchaDefault } }),
            invalidatesTags: [CAPTCHA_SETTINGS_TAG]
        }),
        getWorkspaceCaptchaCounts: builder.query<CaptchaCounts, string>({
            query: (workspaceId) => ({ url: `/workspaces/${workspaceId}/captcha/stats`, method: 'GET' })
        }),
        getFormCaptchaCounts: builder.query<CaptchaCounts, { workspaceId: string; formId: string }>({
            query: ({ workspaceId, formId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/captcha/stats`, method: 'GET' })
        })
    })
});

export const { useGetCaptchaSettingsQuery, useSetCaptchaDefaultMutation, useGetWorkspaceCaptchaCountsQuery, useGetFormCaptchaCountsQuery } = captchaApi;
