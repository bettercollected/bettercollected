const IS_IN_PRODUCTION_MODE = process.env.NEXT_PUBLIC_NODE_ENV === 'production';
const BASE_DEPLOY_PATH = process.env.BASE_DEPLOY_PATH ?? '';

const environments = {
    // build-time configs
    BASE_DEPLOY_PATH,
    // api host configs
    API_ENDPOINT_HOST: process.env.NEXT_PUBLIC_API_ENDPOINT_HOST || 'https://bettercollected.com/api/v1',
    INTERNAL_DOCKER_API_ENDPOINT_HOST: process.env.INTERNAL_DOCKER_API_ENDPOINT_HOST || process.env.API_ENDPOINT_HOST || process.env.NEXT_PUBLIC_API_ENDPOINT_HOST,

    PRIVACY_POLICY_URL: process.env.PRIVACY_POLICY_URL || 'https://bettercollected.com/privacy-policy',
    TERMS_OF_SERVICE_URL: process.env.TERMS_OF_SERVICE_URL || 'https://bettercollected.com/terms-of-service',

    MICROSOFT_CLARITY_TRACKING_CODE: process.env.NEXT_PUBLIC_MICROSOFT_CLARITY_TRACKING_CODE || process.env.MICROSOFT_CLARITY_TRACKING_CODE,

    //workspaces
    MAX_WORKSPACES: process.env.MAX_WORKSPACES || 5,

    // internal configs
    IS_IN_PRODUCTION_MODE,
    NEXT_PUBLIC_NODE_ENV: process.env.NEXT_PUBLIC_NODE_ENV || 'development',
    ELASTIC_APM_SERVER_URL: process.env.ELASTIC_APM_SERVER_URL,
    ELASTIC_APM_SERVICE_NAME: process.env.ELASTIC_APM_SERVICE_NAME,
    ELASTIC_APM_ENVIRONMENT: process.env.ELASTIC_APM_ENVIRONMENT,
    APM_ENABLED: process.env.ELASTIC_APM_SERVER_URL && process.env.ELASTIC_APM_SERVICE_NAME,

    //umami
    UMAMI_WEBSITE_ID: process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID,
    UMAMI_SCRIPT_URL: process.env.UMAMI_SCRIPT_URL,

    CUSTOM_DOMAIN_IP: process.env.CUSTOM_DOMAIN_IP || '135.181.40.62',

    IS_REDUX_LOGGER_DISABLED: true,
    AUTH_ENABLED: false,

    ///Form Webbuilder
    FORM_PRIVACY_POLICY_URL: process.env.FORM_PRIVACY_POLICY_URL ?? 'https://bettercollected.com/privacy-policy',

    // run-time config
    UNSPLASH_ACCESS_KEY: process.env.UNSPLASH_ACCESS_KEY,

    // REfactored Environment Variables
    DASHBOARD_DOMAIN: process.env.NEXT_PUBLIC_DASHBOARD_DOMAIN || 'admin.bettercollected.com',
    FORM_DOMAIN: process.env.NEXT_PUBLIC_FORM_DOMAIN || 'forms.bettercollected.com',
    HTTP_SCHEME: process.env.NEXT_PUBLIC_HTTP_SCHEME || 'https://'
};

export default environments;
