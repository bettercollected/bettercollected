const config = {
    GOOGLE_CLIENT_ID: process.env.GOOGLE_CLIENT_ID,
    GOOGLE_PICKER_API_KEY: process.env.GOOGLE_PICKER_API_KEY,
    API_ENDPOINT_HOST: process.env.API_ENDPOINT_HOST,
    UNSPLASH_ACCESS_KEY: process.env.UNSPLASH_ACCESS_KEY,
    DASHBOARD_DOMAIN: process.env.DASHBOARD_DOMAIN,
    FORM_DOMAIN: process.env.FORM_DOMAIN,
    HTTP_SCHEME: process.env.HTTP_SCHEME || 'https://'
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
