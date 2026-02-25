const config = {
    GOOGLE_CLIENT_ID: process.env.GOOGLE_CLIENT_ID,
    GOOGLE_PICKER_API_KEY: process.env.GOOGLE_PICKER_API_KEY,
    DASHBOARD_DOMAIN: process.env.NEXT_PUBLIC_DASHBOARD_DOMAIN || 'admin.bettercollected.com',
    FORM_DOMAIN: process.env.NEXT_PUBLIC_FORM_DOMAIN || 'forms.bettercollected.com',
    HTTP_SCHEME: process.env.NEXT_PUBLIC_HTTP_SCHEME || 'https://'
};

export type PublicConfigType = typeof config;

// @ts-ignore
export const getPublicConfig = (name: string) => (typeof window === 'undefined' ? config[name] : window.PUBLIC_CONFIG?.[name]);

export async function GET(res: any) {
    return new Response(
        `window.PUBLIC_CONFIG = ${JSON.stringify(config)}
    `,
        {
            headers: {
                'content-type': 'application/javascript'
            }
        }
    );
}
