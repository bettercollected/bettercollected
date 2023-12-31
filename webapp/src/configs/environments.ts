import getConfig from 'next/config';

const config = getConfig();
let publicRuntimeConfig: any = {};
let serverRuntimeConfig: any = {};
if (config && config.publicRuntimeConfig) {
    publicRuntimeConfig = config.publicRuntimeConfig;
}

if (config && config.serverRuntimeConfig) {
    serverRuntimeConfig = config.serverRuntimeConfig;
}

const IS_IN_PRODUCTION_MODE = publicRuntimeConfig.NEXT_PUBLIC_NODE_ENV === 'production';
const BASE_DEPLOY_PATH = process.env.BASE_DEPLOY_PATH ?? '';

const environments = {
    // build-time configs
    BASE_DEPLOY_PATH,
    HTTP_SCHEME: publicRuntimeConfig.HTTP_SCHEME || 'https://',
    CLIENT_DOMAIN: publicRuntimeConfig.CLIENT_DOMAIN || 'localhost:3001',
    ADMIN_DOMAIN: publicRuntimeConfig.ADMIN_DOMAIN || 'localhost:3000',
    // api host configs
    API_ENDPOINT_HOST: publicRuntimeConfig.API_ENDPOINT_HOST,
    INTERNAL_DOCKER_API_ENDPOINT_HOST: serverRuntimeConfig.INTERNAL_DOCKER_API_ENDPOINT_HOST,

    METATAG_TITLE: publicRuntimeConfig.METATAG_TITLE,
    METATAG_DESCRIPTION: publicRuntimeConfig.METATAG_DESCRIPTION,
    METATAG_IMAGE: publicRuntimeConfig.METATAG_IMAGE,
    FORM_PRIVACY_POLICY_URL: publicRuntimeConfig.FORM_PRIVACY_POLICY_URL || 'https://bettercollected.com/privacy-policy',

    // run-time configg
    GA_MEASUREMENT_ID: publicRuntimeConfig.GA_MEASUREMENT_ID,
    MICROSOFT_CLARITY_TRACKING_CODE: publicRuntimeConfig.MICROSOFT_CLARITY_TRACKING_CODE,
    SENTRY_DSN: publicRuntimeConfig.SENTRY_DSN,
    SENTRY_URL: publicRuntimeConfig.SENTRY_URL,
    SENTRY_ORG: publicRuntimeConfig.SENTRY_ORG,
    SENTRY_PROJECT: publicRuntimeConfig.SENTRY_PROJECT,
    SENTRY_AUTH_TOKEN: publicRuntimeConfig.SENTRY_AUTH_TOKEN,
    SENTRY_RELEASE: publicRuntimeConfig.SENTRY_RELEASE,

    //workspaces
    MAX_WORKSPACES: publicRuntimeConfig.MAX_WORKSPACES || 5,

    // Integrations enabled
    ENABLE_GOOGLE: (publicRuntimeConfig.ENABLE_GOOGLE && (publicRuntimeConfig.ENABLE_GOOGLE === 'true' || publicRuntimeConfig.ENABLE_GOOGLE === true)) ?? true,
    ENABLE_TYPEFORM: (publicRuntimeConfig.ENABLE_TYPEFORM && (publicRuntimeConfig.ENABLE_TYPEFORM === 'true' || publicRuntimeConfig.ENABLE_TYPEFORM === true)) ?? true,
    ENABLE_BRAND_COLORS: (publicRuntimeConfig.ENABLE_BRAND_COLORS && (publicRuntimeConfig.ENABLE_BRAND_COLORS === 'true' || publicRuntimeConfig.ENABLE_BRAND_COLORS === true)) ?? false,
    ENABLE_JOYRIDE_TOURS: (publicRuntimeConfig.ENABLE_JOYRIDE_TOURS && (publicRuntimeConfig.ENABLE_JOYRIDE_TOURS === 'true' || publicRuntimeConfig.ENABLE_JOYRIDE_TOURS === true)) ?? false,
    ENABLE_COMMAND_FORM_BUILDERS: (publicRuntimeConfig.ENABLE_COMMAND_FORM_BUILDERS && (publicRuntimeConfig.ENABLE_COMMAND_FORM_BUILDERS === 'true' || publicRuntimeConfig.ENABLE_COMMAND_FORM_BUILDERS === true)) ?? false,
    ENABLE_FORM_BUILDER: (publicRuntimeConfig.ENABLE_FORM_BUILDER && (publicRuntimeConfig.ENABLE_FORM_BUILDER === 'true' || publicRuntimeConfig.ENABLE_FORM_BUILDER === true)) ?? false,
    // internal configs
    IS_IN_PRODUCTION_MODE,
    NEXT_PUBLIC_NODE_ENV: publicRuntimeConfig.NEXT_PUBLIC_NODE_ENV || 'development',
    ELASTIC_APM_SERVER_URL: publicRuntimeConfig.ELASTIC_APM_SERVER_URL,
    ELASTIC_APM_SERVICE_NAME: publicRuntimeConfig.ELASTIC_APM_SERVICE_NAME,
    ELASTIC_APM_ENVIRONMENT: publicRuntimeConfig.ELASTIC_APM_ENVIRONMENT,
    APM_ENABLED: publicRuntimeConfig.ELASTIC_APM_SERVER_URL && publicRuntimeConfig.ELASTIC_APM_SERVICE_NAME,

    //umani
    UMAMI_WEBSITE_ID: publicRuntimeConfig.UMAMI_WEBSITE_ID,
    UMAMI_SCRIPT_URL: publicRuntimeConfig.UMAMI_SCRIPT_URL,

    //actions
    ENABLE_ACTIONS: publicRuntimeConfig.ENABLE_ACTIONS && (publicRuntimeConfig.ENABLE_ACTIONS === 'true' || publicRuntimeConfig.ENABLE_ACTIONS === true)
};

export default environments;
