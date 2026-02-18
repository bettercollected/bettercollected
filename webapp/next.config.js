const { i18n } = require('./next-i18next.config');

const nextConfig = {
    productionBrowserSourceMaps: true,
    compress: true,
    distDir: process.env.NODE_ENV === 'development' ? '.next-dev' : '.next',
    reactStrictMode: true,
    i18n,
    turbopack: {},
    compiler: {
        emotion: true,
        removeConsole: false
    },
    async rewrites() {
        return [
            {
                source: '/script.js',
                destination: 'https://umami.sireto.io/script.js'
            }
        ];
    },
    async headers() {
        return [
            {
                source: '/(.*)',
                headers: [
                    {
                        key: 'X-Frame-Options',
                        value: `ALLOW-FROM https://${process.env.NEXT_PUBLIC_DASHBOARD_DOMAIN}`
                    },
                    {
                        key: 'X-Content-Type-Options',
                        value: 'nosniff'
                    },
                    {
                        key: 'Referrer-Policy',
                        value: 'origin-when-cross-origin'
                    }
                ]
            }
        ];
    },
    images: {
        minimumCacheTTL: 600,
        formats: ['image/avif', 'image/webp'],
        remotePatterns: [
            {
                protocol: 'https',
                hostname: 'lh5.googleusercontent.com',
                port: '',
                pathname: '**'
            },
            {
                protocol: 'https',
                hostname: 'lh3.googleusercontent.com',
                port: '',
                pathname: '**'
            },
            {
                protocol: 'https',
                hostname: '*.googleusercontent.com',
                port: '',
                pathname: '**'
            },
            {
                protocol: 'https',
                hostname: 's3.eu-west-1.wasabisys.com',
                port: '',
                pathname: '**'
            },
            {
                protocol: 'https',
                hostname: 's3.eu-central-1.wasabisys.com',
                port: '',
                pathname: '**'
            },
            {
                protocol: 'https',
                hostname: 'images.typeform.com',
                port: '',
                pathname: '**'
            },
            {
                protocol: 'https',
                hostname: 'sireto.com',
                port: '',
                pathname: '**'
            },
            {
                protocol: 'https',
                hostname: 'images.unsplash.com',
                port: '',
                pathname: '**'
            },
            {
                protocol: 'https',
                hostname: '*.google.com',
                port: '',
                pathname: '**'
            }
        ]
    },

    env: {
        BASE_DEPLOY_PATH: process.env.BASE_DEPLOY_PATH ?? '',
        ELASTIC_APM_SERVER_URL: process.env.ELASTIC_APM_HOST,
        ELASTIC_APM_SERVICE_NAME: process.env.ELASTIC_APM_SERVICE_NAME,
        ELASTIC_APM_ENVIRONMENT: process.env.ELASTIC_APM_ENVIRONMENT,
        ENABLE_BRAND_COLORS: process.env.ENABLE_BRAND_COLORS,
        FORM_PRIVACY_POLICY_URL: process.env.FORM_PRIVACY_POLICY_URL,
        GA_MEASUREMENT_ID: process.env.GA_MEASUREMENT_ID,
        MICROSOFT_CLARITY_TRACKING_CODE: process.env.MICROSOFT_CLARITY_TRACKING_CODE,
        NEXT_PUBLIC_NODE_ENV: process.env.NEXT_PUBLIC_NODE_ENV ?? 'production',

        CONTACT_US_URL: process.env.CONTACT_US_URL,
        CONTACT_US_FORM_NAVIGATION_URL: process.env.CONTACT_US_FORM_NAVIGATION_URL,
        WAITLIST_FORM_URL: process.env.WAITLIST_FORM_URL,
        WAITLIST_FORM_NAVIGATION_URL: process.env.WAITLIST_FORM_NAVIGATION_URL,
        INDIVIDUAL_FORM_URL: process.env.INDIVIDUAL_FORM_URL,
        BUSINESS_FORM_URL: process.env.BUSINESS_FORM_URL,
        ENTERPRISE_FORM_URL: process.env.ENTERPRISE_FORM_URL,
        GOOGLE_IMAGE_DOMAINS: process.env.GOOGLE_IMAGE_DOMAINS,
        CLIENT_DOMAIN: process.env.CLIENT_DOMAIN,
        ADMIN_DOMAIN: process.env.ADMIN_DOMAIN,
        HTTP_SCHEME: process.env.HTTP_SCHEME,
        PRIVACY_POLICY_URL: process.env.PRIVACY_POLICY_URL,
        TERMS_OF_SERVICE_URL: process.env.TERMS_OF_SERVICE_URL,
        WORKSPACE_ID: process.env.WORKSPACE_ID,
        CUSTOM_DOMAIN_IP: process.env.CUSTOM_DOMAIN_IP,
        ENABLE_TYPEFORM: process.env.ENABLE_TYPEFORM || 'true',
        ENABLE_GOOGLE: process.env.ENABLE_GOOGLE || 'true',
        ENABLE_COMMAND_FORM_BUILDERS: process.env.ENABLE_COMMAND_FORM_BUILDERS || 'false',
        ENABLE_CHECK_MY_DATA: process.env.ENABLE_CHECK_MY_DATA || 'false',
        ENABLE_FORM_BUILDER: process.env.ENABLE_FORM_BUILDER || 'false',
        ENABLE_EXPORT_CSV: process.env.ENABLE_EXPORT_CSV || 'false',
        ENABLE_FORM_QR: process.env.ENABLE_FORM_QR || 'false',
        ENABLE_COLLECT_EMAILS: process.env.ENABLE_COLLECT_EMAILS || 'false',
        ENABLE_RESPONSE_EDITING: process.env.ENABLE_RESPONSE_EDITING || 'false',
        ENABLE_SUGGEST_PRICE: process.env.ENABLE_SUGGEST_PRICE,
        MAX_WORKSPACES: process.env.MAX_WORKSPACES || '5',
        API_ENDPOINT_HOST: process.env.API_ENDPOINT_HOST,
        METATAG_TITLE: process.env.METATAG_TITLE,
        METATAG_DESCRIPTION: process.env.METATAG_DESCRIPTION,
        METATAG_IMAGE: process.env.METATAG_IMAGE,
        UMAMI_SCRIPT_URL: process.env.UMAMI_SCRIPT_URL,
        NEXT_PUBLIC_UMAMI_WEBSITE_ID: process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID,
        ENABLE_ACTIONS: process.env.ENABLE_ACTIONS,
        ENABLE_IMPORT_WITH_PICKER: process.env.ENABLE_IMPORT_WITH_PICKER,
        ENABLE_COUPON_CODES: process.env.ENABLE_COUPON_CODES,
        GOOGLE_CLIENT_ID: process.env.GOOGLE_CLIENT_ID,
        GOOGLE_PICKER_API_KEY: process.env.GOOGLE_PICKER_API_KEY,
        CHATWOOT_ENABLE: process.env.CHATWOOT_ENABLE,
        CHATWOOT_DEPLOY_URL: process.env.CHATWOOT_DEPLOY_URL,
        CHATWOOT_WEBSITE_TOKEN: process.env.CHATWOOT_WEBSITE_TOKEN,
        APP_SUMO_PRODUCT_URL: process.env.APP_SUMO_PRODUCT_URL
    }

    // serverRuntimeConfig and publicRuntimeConfig are removed in Next.js 16
    // INTERNAL_DOCKER_API_ENDPOINT_HOST should be used directly via process.env
};

if (process.env.BASE_DEPLOY_PATH) {
    nextConfig['assetPrefix'] = process.env.BASE_DEPLOY_PATH;
    nextConfig['basePath'] = process.env.BASE_DEPLOY_PATH;
}

module.exports = {
    ...nextConfig,
    ...(process.env.NODE_ENV === 'production' && {
        typescript: {
            ignoreBuildErrors: false
        },
        eslint: {
            ignoreDuringBuilds: false
        }
    })
};
