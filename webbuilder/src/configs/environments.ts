const IS_IN_PRODUCTION_MODE = process.env.NEXT_PUBLIC_NODE_ENV === 'production';
const IS_REDUX_LOGGER_DISABLED = process.env.IS_REDUX_LOGGER_DISABLED === 'true';
const BASE_DEPLOY_PATH = process.env.BASE_DEPLOY_PATH ?? '';

const environments = {
    // build-time configs
    BASE_DEPLOY_PATH,

    // api host configs
    API_ENDPOINT_HOST:
        process.env.API_ENDPOINT_HOST || process.env.NEXT_PUBLIC_API_ENDPOINT_HOST,
    NEXT_PUBLIC_API_ENDPOINT_HOST: process.env.NEXT_PUBLIC_API_ENDPOINT_HOST,
    NEXT_PUBLIC_V1_CLIENT_ENDPOINT_DOMAIN:
        process.env.NEXT_PUBLIC_V1_CLIENT_ENDPOINT_DOMAIN,
    NEXT_PUBLIC_V2_CLIENT_ENDPOINT_DOMAIN:
        process.env.NEXT_PUBLIC_V2_CLIENT_ENDPOINT_DOMAIN,

    FORM_PRIVACY_POLICY_URL:
        process.env.FORM_PRIVACY_POLICY_URL ??
        'https://bettercollected.com/privacy-policy',

    // run-time config
    GA_MEASUREMENT_ID: process.env.GA_MEASUREMENT_ID,
    MICROSOFT_CLARITY_TRACKING_CODE: process.env.MICROSOFT_CLARITY_TRACKING_CODE,
    SENTRY_DSN: process.env.SENTRY_DSN,
    SENTRY_URL: process.env.SENTRY_URL,
    SENTRY_ORG: process.env.SENTRY_ORG,
    SENTRY_PROJECT: process.env.SENTRY_PROJECT,
    SENTRY_AUTH_TOKEN: process.env.SENTRY_AUTH_TOKEN,
    SENTRY_RELEASE: process.env.SENTRY_RELEASE,
    UNSPLASH_APPLICATION_ID: process.env.UNSPLASH_APPLICATION_ID,
    UNSPLASH_ACCESS_KEY: process.env.UNSPLASH_ACCESS_KEY ?? '',
    NEXT_PUBLIC_UNSPLASH_ACCESS_KEY: process.env.NEXT_PUBLIC_UNSPLASH_ACCESS_KEY,
    UNSPLASH_SECRET_KEY: process.env.UNSPLASH_SECRET_KEY,
    UNSPLASH_API_URL: process.env.UNSPLASH_API_URL ?? 'https://api.unsplash.com/',

    // Integrations enabled
    ENABLE_BRAND_COLORS:
        (process.env.ENABLE_BRAND_COLORS &&
            (process.env.ENABLE_BRAND_COLORS === 'true' ||
                // @ts-ignore
                process.env.ENABLE_BRAND_COLORS === true)) ??
        false,
    ENABLE_JOYRIDE_TOURS:
        (process.env.ENABLE_JOYRIDE_TOURS &&
            (process.env.ENABLE_JOYRIDE_TOURS === 'true' ||
                // @ts-ignore
                process.env.ENABLE_JOYRIDE_TOURS === true)) ??
        false,

    // internal configs
    IS_IN_PRODUCTION_MODE,
    IS_REDUX_LOGGER_DISABLED,
    NEXT_PUBLIC_NODE_ENV: process.env.NEXT_PUBLIC_NODE_ENV ?? 'development',
    NEXT_PUBLIC_DASHBOARD_DOMAIN: process.env.NEXT_PUBLIC_DASHBOARD_DOMAIN ?? '',
    NEXT_PUBLIC_HTTP_SCHEME: process.env.NEXT_PUBLIC_HTTP_SCHEME ?? 'https',
    ELASTIC_APM_SERVER_URL: process.env.ELASTIC_APM_SERVER_URL,
    ELASTIC_APM_SERVICE_NAME: process.env.ELASTIC_APM_SERVICE_NAME,
    ELASTIC_APM_ENVIRONMENT: process.env.ELASTIC_APM_ENVIRONMENT,
    AUTH_ENABLED: process.env.AUTH_ENABLED,
    APM_ENABLED:
        process.env.ELASTIC_APM_SERVER_URL && process.env.ELASTIC_APM_SERVICE_NAME
};

export default environments;
