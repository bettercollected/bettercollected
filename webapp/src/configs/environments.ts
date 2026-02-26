const environments = {
    // api host configs
    API_ENDPOINT_HOST: process.env.NEXT_PUBLIC_API_ENDPOINT_HOST || 'https://bettercollected.com/api/v1',
    INTERNAL_DOCKER_API_ENDPOINT_HOST: process.env.INTERNAL_DOCKER_API_ENDPOINT_HOST || process.env.API_ENDPOINT_HOST || process.env.NEXT_PUBLIC_API_ENDPOINT_HOST,

    // internal configs
    NEXT_PUBLIC_NODE_ENV: process.env.NEXT_PUBLIC_NODE_ENV || 'development',

    //umami
    UMAMI_WEBSITE_ID: process.env.UMAMI_WEBSITE_ID,
    UMAMI_SCRIPT_URL: process.env.UMAMI_SCRIPT_URL,

    CUSTOM_DOMAIN_IP: process.env.CUSTOM_DOMAIN_IP || '135.181.40.62',

    ///Form Webbuilder
    FORM_PRIVACY_POLICY_URL: process.env.FORM_PRIVACY_POLICY_URL ?? 'https://bettercollected.com/privacy-policy',

    // REfactored Environment Variables
    DASHBOARD_DOMAIN: process.env.DASHBOARD_DOMAIN || 'admin.bettercollected.com',
    FORM_DOMAIN: process.env.FORM_DOMAIN || 'forms.bettercollected.com',
    HTTP_SCHEME: process.env.HTTP_SCHEME || 'https://'
};

export default environments;
