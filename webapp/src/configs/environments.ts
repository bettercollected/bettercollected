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
    API_ENDPOINT_HOST: publicRuntimeConfig.API_ENDPOINT_HOST || process.env.API_ENDPOINT_HOST || 'https://bettercollected.io/api/v1',
    INTERNAL_DOCKER_API_ENDPOINT_HOST: serverRuntimeConfig.INTERNAL_DOCKER_API_ENDPOINT_HOST,

    METATAG_TITLE: publicRuntimeConfig.METATAG_TITLE,
    METATAG_DESCRIPTION: publicRuntimeConfig.METATAG_DESCRIPTION,
    METATAG_IMAGE: publicRuntimeConfig.METATAG_IMAGE,
    PRIVACY_POLICY_URL: publicRuntimeConfig.PRIVACY_POLICY_URL || 'https://bettercollected.com/privacy-policy',
    TERMS_OF_SERVICE_URL: publicRuntimeConfig.TERMS_OF_SERVICE_URL || 'https://bettercollected.com/terms-of-service',

    // run-time config
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
    ENABLE_EXPORT_CSV: (publicRuntimeConfig.ENABLE_EXPORT_CSV && (publicRuntimeConfig.ENABLE_EXPORT_CSV === 'true' || publicRuntimeConfig.ENABLE_EXPORT_CSV === true)) ?? false,
    ENABLE_FORM_QR: (publicRuntimeConfig.ENABLE_FORM_QR && (publicRuntimeConfig.ENABLE_FORM_QR === 'true' || publicRuntimeConfig.ENABLE_FORM_QR === true)) ?? false,
    ENABLE_COLLECT_EMAILS: (publicRuntimeConfig.ENABLE_COLLECT_EMAILS && (publicRuntimeConfig.ENABLE_COLLECT_EMAILS === 'true' || publicRuntimeConfig.ENABLE_COLLECT_EMAILS === true)) ?? false,
    ENABLE_RESPONSE_EDITING: (publicRuntimeConfig.ENABLE_RESPONSE_EDITING && (publicRuntimeConfig.ENABLE_RESPONSE_EDITING === 'true' || publicRuntimeConfig.ENABLE_RESPONSE_EDITING === true)) ?? false,

    // V2 builder
    ENABLE_V2_BUILDER: (publicRuntimeConfig.ENABLE_V2_BUILDER && (publicRuntimeConfig.ENABLE_V2_BUILDER === 'true' || publicRuntimeConfig.ENABLE_V2_BUILDER === true)) ?? false,
    V2_BUILDER_DOMAIN: publicRuntimeConfig.V2_BUILDER_DOMAIN || '',
    V2_FORM_DOMAIN: publicRuntimeConfig.V2_FORM_DOMAIN,

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

    ENABLE_ACTIONS: publicRuntimeConfig.ENABLE_ACTIONS && (publicRuntimeConfig.ENABLE_ACTIONS === 'true' || publicRuntimeConfig.ENABLE_ACTIONS === true),
    ENABLE_IMPORT_WITH_PICKER: publicRuntimeConfig.ENABLE_IMPORT_WITH_PICKER && (publicRuntimeConfig.ENABLE_IMPORT_WITH_PICKER === 'true' || publicRuntimeConfig.ENABLE_IMPORT_WITH_PICKER === true),
    ENABLE_COUPON_CODES: publicRuntimeConfig.ENABLE_COUPON_CODES && (publicRuntimeConfig.ENABLE_COUPON_CODES === 'true' || publicRuntimeConfig.ENABLE_COUPON_CODES === true),

    // google picker api
    GOOGLE_CLIENT_ID: publicRuntimeConfig.GOOGLE_CLIENT_ID,
    GOOGLE_PICKER_API_KEY: publicRuntimeConfig.GOOGLE_PICKER_API_KEY,

    //CHATWOOT
    CHATWOOT_ENABLE: publicRuntimeConfig.CHATWOOT_ENABLE && (publicRuntimeConfig.CHATWOOT_ENABLE === 'true' || publicRuntimeConfig.CHATWOOT_ENABLE === true),
    CHATWOOT_DEPLOY_URL: publicRuntimeConfig.CHATWOOT_DEPLOY_URL ?? 'https://help.bettercollected.com',
    CHATWOOT_WEBSITE_TOKEN: publicRuntimeConfig.CHATWOOT_WEBSITE_TOKEN,

    APP_SUMO_PRODUCT_URL: publicRuntimeConfig.APP_SUMO_PRODUCT_URL ?? 'https://appsumo.com/products/bettercollected',

    // Enable Price Suggestion
    ENABLE_SUGGEST_PRICE: publicRuntimeConfig.ENABLE_SUGGEST_PRICE && (publicRuntimeConfig.ENABLE_SUGGEST_PRICE === 'true' || publicRuntimeConfig.ENABLE_SUGGEST_PRICE === true),

    IS_REDUX_LOGGER_DISABLED: true,
    AUTH_ENABLED: true,

    ///Form Webbuilder
    NEXT_PUBLIC_API_ENDPOINT_HOST: process.env.NEXT_PUBLIC_API_ENDPOINT_HOST|| "https://bettercollected.io/api/v1",
    NEXT_PUBLIC_V1_CLIENT_ENDPOINT_DOMAIN: process.env.NEXT_PUBLIC_V1_CLIENT_ENDPOINT_DOMAIN,
    NEXT_PUBLIC_V2_CLIENT_ENDPOINT_DOMAIN: process.env.NEXT_PUBLIC_V2_CLIENT_ENDPOINT_DOMAIN || 'forms.bettercollected.io',
    FORM_PRIVACY_POLICY_URL: process.env.FORM_PRIVACY_POLICY_URL ?? 'https://bettercollected.com/privacy-policy',

    // run-time config
    UNSPLASH_APPLICATION_ID: process.env.UNSPLASH_APPLICATION_ID,
    UNSPLASH_ACCESS_KEY: process.env.UNSPLASH_ACCESS_KEY ?? 'cjNqTgaSqmYzOZETsWrivtF1ayn4PGzy_NPWZDkZG_A',
    NEXT_PUBLIC_UNSPLASH_ACCESS_KEY: process.env.NEXT_PUBLIC_UNSPLASH_ACCESS_KEY || '___NEXT_PUBLIC_UNSPLASH_ACCESS_KEY___',
    UNSPLASH_SECRET_KEY: process.env.UNSPLASH_SECRET_KEY,
    UNSPLASH_API_URL: process.env.UNSPLASH_API_URL ?? 'https://api.unsplash.com/',

    // internal configs
    NEXT_PUBLIC_DASHBOARD_DOMAIN: process.env.NEXT_PUBLIC_DASHBOARD_DOMAIN ?? '',
    NEXT_PUBLIC_HTTP_SCHEME: process.env.NEXT_PUBLIC_HTTP_SCHEME ?? 'https'
};

export default environments;
