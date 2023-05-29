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

    // run-time configg
    GA_MEASUREMENT_ID: publicRuntimeConfig.GA_MEASUREMENT_ID,
    MICROSOFT_CLARITY_TRACKING_CODE: publicRuntimeConfig.MICROSOFT_CLARITY_TRACKING_CODE,
    SENTRY_DSN: publicRuntimeConfig.SENTRY_DSN,
    SENTRY_URL: publicRuntimeConfig.SENTRY_URL,
    SENTRY_ORG: publicRuntimeConfig.SENTRY_ORG,
    SENTRY_PROJECT: publicRuntimeConfig.SENTRY_PROJECT,
    SENTRY_AUTH_TOKEN: publicRuntimeConfig.SENTRY_AUTH_TOKEN,
    SENTRY_RELEASE: publicRuntimeConfig.SENTRY_RELEASE,

    // Integrations enabled
    ENABLE_GOOGLE: (publicRuntimeConfig.ENABLE_GOOGLE && (publicRuntimeConfig.ENABLE_GOOGLE === 'true' || publicRuntimeConfig.ENABLE_GOOGLE === true)) ?? false,
    ENABLE_TYPEFORM: (publicRuntimeConfig.ENABLE_TYPEFORM && (publicRuntimeConfig.ENABLE_TYPEFORM === 'true' || publicRuntimeConfig.ENABLE_TYPEFORM === true)) ?? false,
    ENABLE_BRAND_COLORS: (publicRuntimeConfig.ENABLE_BRAND_COLORS && (publicRuntimeConfig.ENABLE_BRAND_COLORS === 'true' || publicRuntimeConfig.ENABLE_BRAND_COLORS === true)) ?? false,
    ENABLE_JOYRIDE_TOURS: (publicRuntimeConfig.ENABLE_JOYRIDE_TOURS && (publicRuntimeConfig.ENABLE_JOYRIDE_TOURS === 'true' || publicRuntimeConfig.ENABLE_JOYRIDE_TOURS === true)) ?? false,
    // internal configs
    IS_IN_PRODUCTION_MODE,
    NEXT_PUBLIC_NODE_ENV: publicRuntimeConfig.NEXT_PUBLIC_NODE_ENV || 'development',
    ELASTIC_APM_SERVER_URL: publicRuntimeConfig.ELASTIC_APM_SERVER_URL,
    ELASTIC_APM_SERVICE_NAME: publicRuntimeConfig.ELASTIC_APM_SERVICE_NAME,
    ELASTIC_APM_ENVIRONMENT: publicRuntimeConfig.ELASTIC_APM_ENVIRONMENT,
    APM_ENABLED: publicRuntimeConfig.ELASTIC_APM_SERVER_URL && publicRuntimeConfig.ELASTIC_APM_SERVICE_NAME
};

export default environments;
