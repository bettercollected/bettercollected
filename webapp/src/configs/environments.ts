const IS_IN_PRODUCTION_MODE = process.env.NEXT_PUBLIC_NODE_ENV === 'production';
const BASE_DEPLOY_PATH = process.env.BASE_DEPLOY_PATH ?? '';

const environments = {
    // build-time configs
    BASE_DEPLOY_PATH,
    CLIENT_DOMAIN: process.env.CLIENT_DOMAIN || 'localhost:3001',
    ADMIN_DOMAIN: process.env.ADMIN_DOMAIN || 'localhost:3000',
    // api host configs
    API_ENDPOINT_HOST: process.env.NEXT_PUBLIC_API_ENDPOINT_HOST || 'https://bettercollected.com/api/v1',
    INTERNAL_DOCKER_API_ENDPOINT_HOST: process.env.INTERNAL_DOCKER_API_ENDPOINT_HOST || process.env.API_ENDPOINT_HOST || process.env.NEXT_PUBLIC_API_ENDPOINT_HOST,

    METATAG_TITLE: process.env.METATAG_TITLE,
    METATAG_DESCRIPTION: process.env.METATAG_DESCRIPTION,
    METATAG_IMAGE: process.env.METATAG_IMAGE,
    PRIVACY_POLICY_URL: process.env.PRIVACY_POLICY_URL || 'https://bettercollected.com/privacy-policy',
    TERMS_OF_SERVICE_URL: process.env.TERMS_OF_SERVICE_URL || 'https://bettercollected.com/terms-of-service',

    // run-time config
    GA_MEASUREMENT_ID: process.env.GA_MEASUREMENT_ID,
    MICROSOFT_CLARITY_TRACKING_CODE: process.env.NEXT_PUBLIC_MICROSOFT_CLARITY_TRACKING_CODE || process.env.MICROSOFT_CLARITY_TRACKING_CODE,

    //workspaces
    MAX_WORKSPACES: process.env.MAX_WORKSPACES || 5,

    // Integrations enabled
    ENABLE_GOOGLE: (process.env.ENABLE_GOOGLE && process.env.ENABLE_GOOGLE === 'true') ?? true,
    ENABLE_TYPEFORM: (process.env.ENABLE_TYPEFORM && process.env.ENABLE_TYPEFORM === 'true') ?? true,
    ENABLE_BRAND_COLORS: (process.env.ENABLE_BRAND_COLORS && process.env.ENABLE_BRAND_COLORS === 'true') ?? false,
    ENABLE_COMMAND_FORM_BUILDERS: (process.env.ENABLE_COMMAND_FORM_BUILDERS && process.env.ENABLE_COMMAND_FORM_BUILDERS === 'true') ?? false,
    ENABLE_FORM_BUILDER: (process.env.ENABLE_FORM_BUILDER && process.env.ENABLE_FORM_BUILDER === 'true') ?? false,
    ENABLE_EXPORT_CSV: (process.env.ENABLE_EXPORT_CSV && process.env.ENABLE_EXPORT_CSV === 'true') ?? false,
    ENABLE_FORM_QR: (process.env.ENABLE_FORM_QR && process.env.ENABLE_FORM_QR === 'true') ?? false,
    ENABLE_COLLECT_EMAILS: (process.env.ENABLE_COLLECT_EMAILS && process.env.ENABLE_COLLECT_EMAILS === 'true') ?? false,
    ENABLE_RESPONSE_EDITING: (process.env.ENABLE_RESPONSE_EDITING && process.env.ENABLE_RESPONSE_EDITING === 'true') ?? false,

    // V2 builder
    ENABLE_V2_BUILDER: (process.env.ENABLE_V2_BUILDER && process.env.ENABLE_V2_BUILDER === 'true') ?? false,

    // internal configs
    IS_IN_PRODUCTION_MODE,
    NEXT_PUBLIC_NODE_ENV: process.env.NEXT_PUBLIC_NODE_ENV || 'development',
    ELASTIC_APM_SERVER_URL: process.env.ELASTIC_APM_SERVER_URL,
    ELASTIC_APM_SERVICE_NAME: process.env.ELASTIC_APM_SERVICE_NAME,
    ELASTIC_APM_ENVIRONMENT: process.env.ELASTIC_APM_ENVIRONMENT,
    APM_ENABLED: process.env.ELASTIC_APM_SERVER_URL && process.env.ELASTIC_APM_SERVICE_NAME,

    //umani
    UMAMI_WEBSITE_ID: process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID,
    UMAMI_SCRIPT_URL: process.env.UMAMI_SCRIPT_URL,

    ENABLE_ACTIONS: process.env.ENABLE_ACTIONS && process.env.ENABLE_ACTIONS === 'true',
    ENABLE_IMPORT_WITH_PICKER: process.env.ENABLE_IMPORT_WITH_PICKER && process.env.ENABLE_IMPORT_WITH_PICKER === 'true',
    ENABLE_COUPON_CODES: process.env.ENABLE_COUPON_CODES && process.env.ENABLE_COUPON_CODES === 'true',

    // google picker api
    GOOGLE_CLIENT_ID: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '',
    GOOGLE_PICKER_API_KEY: process.env.NEXT_PUBLIC_GOOGLE_PICKER_API_KEY || '',

    CUSTOM_DOMAIN_IP: process.env.CUSTOM_DOMAIN_IP || '135.181.40.62',

    //CHATWOOT
    CHATWOOT_ENABLE: process.env.CHATWOOT_ENABLE && process.env.CHATWOOT_ENABLE === 'true',
    CHATWOOT_DEPLOY_URL: process.env.CHATWOOT_DEPLOY_URL ?? 'https://help.bettercollected.com',
    CHATWOOT_WEBSITE_TOKEN: process.env.CHATWOOT_WEBSITE_TOKEN,

    APP_SUMO_PRODUCT_URL: process.env.APP_SUMO_PRODUCT_URL ?? 'https://appsumo.com/products/bettercollected',

    // Enable Price Suggestion
    ENABLE_SUGGEST_PRICE: process.env.ENABLE_SUGGEST_PRICE && process.env.ENABLE_SUGGEST_PRICE === 'true',

    IS_REDUX_LOGGER_DISABLED: true,
    AUTH_ENABLED: false,

    ///Form Webbuilder
    FORM_PRIVACY_POLICY_URL: process.env.FORM_PRIVACY_POLICY_URL ?? 'https://bettercollected.com/privacy-policy',

    // run-time config
    UNSPLASH_ACCESS_KEY: process.env.NEXT_PUBLIC_UNSPLASH_ACCESS_KEY,

    // REfactored Environment Variables
    DASHBOARD_DOMAIN: process.env.NEXT_PUBLIC_DASHBOARD_DOMAIN || 'admin.bettercollected.com',
    FORM_DOMAIN: process.env.NEXT_PUBLIC_FORM_DOMAIN || 'forms.bettercollected.com',
    HTTP_SCHEME: process.env.NEXT_PUBLIC_HTTP_SCHEME || 'https://'
};

export default environments;
