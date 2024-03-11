/** @type {import('next').NextConfig} */

const runtimeCaching = require('next-pwa/cache');

const withPlugins = require('next-compose-plugins');

const { withSentryConfig } = require('@sentry/nextjs');

const { i18n } = require('./next-i18next.config');

const getHostnameFromRegex = (url) => {
    // run against regex
    const matches = url.match(/^https?:\/\/([^/?#]+)(?:[/?#]|$)/i);
    // extract hostname (will be empty string if no match is found)
    return matches ? matches[1] : '';
};

const googleUrls = process.env.GOOGLE_IMAGE_DOMAINS ? process.env.GOOGLE_IMAGE_DOMAINS.split(',') : null;
const googleImageDomains = [];

if (googleUrls && Array.isArray(googleUrls)) {
    googleUrls.map((url) => {
        const domain = getHostnameFromRegex(url);
        if (domain) googleImageDomains.push(domain);
    });
}

const withPWA = require('next-pwa')({
    dest: 'public',
    disable: process.env.NODE_ENV === 'development',
    runtimeCaching,
    buildExcludes: [/middleware-manifest\.json$/]
});

const nextConfig = {
    productionBrowserSourceMaps: true,
    compress: true,
    distDir: process.env.NODE_ENV === 'development' ? '.next-dev' : '.next',
    reactStrictMode: true,
    swcMinify: false,
    i18n,
    optimizeFonts: true,
    compiler: {
        emotion: true,
        removeConsole: false
    },

    async headers() {
        return [
            {
                source: '/(.*)',
                headers: [
                    {
                        key: 'X-Frame-Options',
                        value: 'DENY'
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
    // Optional build-time configuration options
    sentry: {
        // See the sections below for information on the following options:
        //   'Configure Source Maps':
        //     - disableServerWebpackPlugin
        //     - disableClientWebpackPlugin
        //     - hideSourceMaps
        //     - widenClientFileUpload
        //   'Configure Legacy Browser Support':
        //     - transpileClientSDK
        //   'Configure Serverside Auto-instrumentation':
        //     - autoInstrumentServerFunctions
        //     - excludeServerRoutes
        //   'Configure Tunneling to avoid Ad-Blockers':
        //     - tunnelRoute
    },
    images: {
        minimumCacheTTL: 600,
        formats: ['image/avif', 'image/webp'],
        domains: [...googleImageDomains, 'images.typeform.com', 'lh5.googleusercontent.com', 'lh3.googleusercontent.com', 's3.eu-west-1.wasabisys.com', 's3.eu-central-1.wasabisys.com', 'sireto.com']
    },
    serverRuntimeConfig: {
        // Use this environment separately if you are running your webapp through docker compose
        INTERNAL_DOCKER_API_ENDPOINT_HOST: process.env.INTERNAL_DOCKER_API_ENDPOINT_HOST || process.env.API_ENDPOINT_HOST
    },
    publicRuntimeConfig: {
        CONTACT_US_URL: process.env.CONTACT_US_URL,
        CONTACT_US_FORM_NAVIGATION_URL: process.env.CONTACT_US_FORM_NAVIGATION_URL,
        GA_MEASUREMENT_ID: process.env.GA_MEASUREMENT_ID,
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
        MICROSOFT_CLARITY_TRACKING_CODE: process.env.MICROSOFT_CLARITY_TRACKING_CODE,

        NEXT_PUBLIC_NODE_ENV: process.env.NEXT_PUBLIC_NODE_ENV || 'production',

        // Custom Domain Variables
        IS_CUSTOM_DOMAIN: process.env.IS_CUSTOM_DOMAIN || false,
        WORKSPACE_ID: process.env.WORKSPACE_ID,
        CUSTOM_DOMAIN: process.env.CUSTOM_DOMAIN,
        CUSTOM_DOMAIN_JSON: process.env.CUSTOM_DOMAIN_JSON,
        ENABLE_TYPEFORM: process.env.ENABLE_TYPEFORM || true,
        ENABLE_GOOGLE: process.env.ENABLE_GOOGLE || true,
        ENABLE_COMMAND_FORM_BUILDERS: process.env.ENABLE_COMMAND_FORM_BUILDERS || false,
        ENABLE_CHECK_MY_DATA: process.env.ENABLE_CHECK_MY_DATA || false,
        ENABLE_BRAND_COLORS: process.env.ENABLE_BRAND_COLORS || false,
        ENABLE_JOYRIDE_TOURS: process.env.ENABLE_JOYRIDE_TOURS || false,
        ENABLE_FORM_BUILDER: process.env.ENABLE_FORM_BUILDER || false,
        ENABLE_EXPORT_CSV: process.env.ENABLE_EXPORT_CSV || false,
        ENABLE_FORM_QR: process.env.ENABLE_FORM_QR || false,
        ENABLE_COLLECT_EMAILS: process.env.ENABLE_COLLECT_EMAILS || false,
        ENABLE_RESPONSE_EDITING: process.env.ENABLE_RESPONSE_EDITING || false,

        // V2 builder
        ENABLE_V2_BUILDER: process.env.ENABLE_V2_BUILDER || false,
        V2_BUILDER_DOMAIN: process.env.V2_BUILDER_DOMAIN || '',
        V2_FORM_DOMAIN: process.env.V2_FORM_DOMAIN || '',

        // Enable Suggest price allowing user to get pro feature for free
        ENABLE_SUGGEST_PRICE: process.env.ENABLE_SUGGEST_PRICE,

        MAX_WORKSPACES: process.env.MAX_WORKSPACES || 5,

        // api hosts
        API_ENDPOINT_HOST: process.env.API_ENDPOINT_HOST,

        // Sentry
        SENTRY_DSN: process.env.SENTRY_DSN,
        SENTRY_URL: process.env.SENTRY_URL,
        SENTRY_ORG: process.env.SENTRY_ORG,
        SENTRY_PROJECT: process.env.SENTRY_PROJECT,
        SENTRY_AUTH_TOKEN: process.env.SENTRY_AUTH_TOKEN,
        SENTRY_RELEASE: process.env.SENTRY_RELEASE,

        // metatags
        METATAG_TITLE: process.env.METATAG_TITLE,
        METATAG_DESCRIPTION: process.env.METATAG_DESCRIPTION,
        METATAG_IMAGE: process.env.METATAG_IMAGE,
        ELASTIC_APM_SERVER_URL: process.env.ELASTIC_APM_HOST,
        ELASTIC_APM_SERVICE_NAME: process.env.ELASTIC_APM_SERVICE_NAME,
        ELASTIC_APM_ENVIRONMENT: process.env.ELASTIC_APM_ENVIRONMENT,

        //unami
        UMAMI_SCRIPT_URL: process.env.UMAMI_SCRIPT_URL,
        UMAMI_WEBSITE_ID: process.env.UMAMI_WEBSITE_ID,

        //integrations
        ENABLE_ACTIONS: process.env.ENABLE_ACTIONS,
        ENABLE_IMPORT_WITH_PICKER: process.env.ENABLE_IMPORT_WITH_PICKER,
        ENABLE_COUPON_CODES: process.env.ENABLE_COUPON_CODES,

        //Google Picker API
        GOOGLE_CLIENT_ID: process.env.GOOGLE_CLIENT_ID,
        GOOGLE_PICKER_API_KEY: process.env.GOOGLE_PICKER_API_KEY,

        // Chatwoot
        CHATWOOT_ENABLE: process.env.CHATWOOT_ENABLE,
        CHATWOOT_DEPLOY_URL: process.env.CHATWOOT_DEPLOY_URL,
        CHATWOOT_WEBSITE_TOKEN: process.env.CHATWOOT_WEBSITE_TOKEN,

        // App Sumo
        APP_SUMO_PRODUCT_URL: process.env.APP_SUMO_PRODUCT_URL
    }
};

if (process.env.BASE_DEPLOY_PATH) {
    nextConfig['assetPrefix'] = process.env.BASE_DEPLOY_PATH;
    nextConfig['basePath'] = process.env.BASE_DEPLOY_PATH;
}

const sentryWebpackPluginOptions = {
    // Additional config options for the Sentry Webpack plugin. Keep in mind that
    // the following options are set automatically, and overriding them is not
    // recommended:
    //   release, url, authToken, configFile, stripPrefix,
    //   urlPrefix, include, ignore

    dryRun: process.env.NODE_ENV !== 'production',
    silent: true, // Suppresses all logs
    attachStacktrace: true,
    release: process.env.SENTRY_RELEASE,
    url: process.env.SENTRY_URL,
    org: process.env.SENTRY_ORG,
    project: process.env.SENTRY_PROJECT,
    authToken: process.env.SENTRY_AUTH_TOKEN,
    sourcemaps: {
        // Specify the directory containing build artifacts
        assets: './**',
        // Don't upload the source maps of dependencies
        ignore: ['./node_modules/**']
    },
    debug: process.env.NEXT_PUBLIC_NODE_ENV !== 'production'

    // For all available options, see:
    // https://github.com/getsentry/sentry-webpack-plugin#options.
};

const nextConfigWithPWA = withPWA({
    ...nextConfig,
    ...(process.env.NODE_ENV === 'production' && {
        typescript: {
            ignoreBuildErrors: false
        },
        eslint: {
            ignoreDuringBuilds: false
        }
    })
});

const nextConfigWithSentryIfEnabled =
    !!process.env.SENTRY_DSN && !!process.env.SENTRY_URL && !!process.env.SENTRY_ORG && !!process.env.SENTRY_PROJECT && !!process.env.SENTRY_RELEASE
        ? withSentryConfig({ ...nextConfigWithPWA, devtool: 'source-map' }, sentryWebpackPluginOptions)
        : nextConfigWithPWA;

module.exports = nextConfigWithSentryIfEnabled;
