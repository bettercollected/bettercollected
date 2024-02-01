import nextPwa from 'next-pwa';
import runtimeCaching from 'next-pwa/cache.js';

import { withSentryConfig } from '@sentry/nextjs';

import i18nextConfig from './next-i18next.config.js';

const i18n = i18nextConfig.i18n;

const imageDomains = process.env.IMAGE_DOMAINS
    ? process.env.IMAGE_DOMAINS.split(',')
    : null;
const imageDomainsWithOnlyHostname = [];

function getHostnameFromRegex(url) {
    // run against regex
    const matches = url.match(/^https?:\/\/([^/?#]+)(?:[/?#]|$)/i);
    // extract hostname (will be empty string if no match is found)
    return matches ? matches[1] : '';
}

if (imageDomains && Array.isArray(imageDomains)) {
    imageDomains.forEach((domain) => {
        const hostname = getHostnameFromRegex(domain);
        if (hostname) {
            imageDomainsWithOnlyHostname.push(hostname);
        }
    });
}

/** @type {import('next').NextConfig} */
const nextConfig = {
    productionBrowserSourceMaps: true,
    compress: true,
    distDir: process.env.NODE_ENV === 'production' ? '.next' : '.next-dev',
    reactStrictMode: true,
    optimizeFonts: true,
    i18n,
    devIndicators: {
        buildActivityPosition: 'bottom-right'
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

    images: {
        minimumCacheTTL: 600,
        formats: ['image/avif', 'image/webp'],
        domains: imageDomainsWithOnlyHostname
    },

    env: {
        BASE_DEPLOY_PATH: process.env.BASE_DEPLOY_PATH ?? '',
        ELASTIC_APM_SERVER_URL: process.env.ELASTIC_APM_HOST,
        ELASTIC_APM_SERVICE_NAME: process.env.ELASTIC_APM_SERVICE_NAME,
        ELASTIC_APM_ENVIRONMENT: process.env.ELASTIC_APM_ENVIRONMENT,
        ENABLE_BRAND_COLORS: process.env.ENABLE_BRAND_COLORS,
        ENABLE_JOYRIDE_TOURS: process.env.ENABLE_JOYRIDE_TOURS,
        FORM_PRIVACY_POLICY_URL: process.env.FORM_PRIVACY_POLICY_URL,
        GA_MEASUREMENT_ID: process.env.GA_MEASUREMENT_ID,
        MICROSOFT_CLARITY_TRACKING_CODE: process.env.MICROSOFT_CLARITY_TRACKING_CODE,
        NEXT_PUBLIC_NODE_ENV: process.env.NEXT_PUBLIC_NODE_ENV ?? 'production'
    }
};

if (process.env.BASE_DEPLOY_PATH) {
    nextConfig.assetPrefix = process.env.BASE_DEPLOY_PATH;
    nextConfig.basePath = process.env.BASE_DEPLOY_PATH;
}

const withPWA = nextPwa({
    dest: 'public',
    disable: process.env.NODE_ENV === 'development',
    runtimeCaching,
    buildExcludes: [/middleware-manifest\.json$/]
});
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

const nextConfigWithSentryIfEnabled =
    !!process.env.SENTRY_DSN &&
    !!process.env.SENTRY_URL &&
    !!process.env.SENTRY_ORG &&
    !!process.env.SENTRY_PROJECT &&
    !!process.env.SENTRY_RELEASE
        ? withSentryConfig(
              { ...nextConfigWithPWA, devtool: 'source-map' },
              sentryWebpackPluginOptions
          )
        : nextConfigWithPWA;

export default nextConfigWithSentryIfEnabled;
