// globals.d.ts (or css.d.ts)
declare module '*.css';

interface Window {
    PUBLIC_CONFIG: {
        DASHBOARD_DOMAIN: string;
        FORM_DOMAIN: string;
        HTTP_SCHEME: string;
        API_ENDPOINT_HOST: string;
    }
}