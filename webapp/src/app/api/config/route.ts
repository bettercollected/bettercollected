const config: any = {
    GOOGLE_CLIENT_ID: process.env.GOOGLE_CLIENT_ID || '',
    GOOGLE_PICKER_API_KEY: process.env.GOOGLE_PICKER_API_KEY
};

// @ts-ignore
export const getPublicConfig = (name: string) => (typeof window === 'undefined' ? config[name] : window.PUBLIC_CONFIG[name]);

export async function GET(res: any) {
    return new Response(`window.PUBLIC_CONFIG = ${JSON.stringify(config)}`, {
        headers: {
            'content-type': 'application/javascript'
        }
    });
}
