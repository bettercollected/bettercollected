const IS_IN_PRODUCTION_MODE = process.env.NEXT_PUBLIC_NODE_ENV === 'production';
const IS_REDUX_LOGGER_DISABLED = process.env.IS_REDUX_LOGGER_DISABLED === 'true';
const BASE_DEPLOY_PATH = process.env.BASE_DEPLOY_PATH ?? '';

const environments = {
    // build-time configs
    BASE_DEPLOY_PATH,

    // api host configs
    API_ENDPOINT_HOST: process.env.API_ENDPOINT_HOST,

    FORM_PRIVACY_POLICY_URL:
        process.env.FORM_PRIVACY_POLICY_URL ??
        'https://bettercollected.com/privacy-policy',

    // run-time configg
    GA_MEASUREMENT_ID: process.env.GA_MEASUREMENT_ID,
    MICROSOFT_CLARITY_TRACKING_CODE: process.env.MICROSOFT_CLARITY_TRACKING_CODE,
    SENTRY_DSN: process.env.SENTRY_DSN,
    SENTRY_URL: process.env.SENTRY_URL,
    SENTRY_ORG: process.env.SENTRY_ORG,
    SENTRY_PROJECT: process.env.SENTRY_PROJECT,
    SENTRY_AUTH_TOKEN: process.env.SENTRY_AUTH_TOKEN,
    SENTRY_RELEASE: process.env.SENTRY_RELEASE,

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
    ELASTIC_APM_SERVER_URL: process.env.ELASTIC_APM_SERVER_URL,
    ELASTIC_APM_SERVICE_NAME: process.env.ELASTIC_APM_SERVICE_NAME,
    ELASTIC_APM_ENVIRONMENT: process.env.ELASTIC_APM_ENVIRONMENT,
    APM_ENABLED:
        process.env.ELASTIC_APM_SERVER_URL && process.env.ELASTIC_APM_SERVICE_NAME
};

export default environments;
