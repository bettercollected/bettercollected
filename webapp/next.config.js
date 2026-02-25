const { i18n } = require('./next-i18next.config');

const nextConfig = {
    productionBrowserSourceMaps: true,
    compress: true,
    distDir: process.env.NODE_ENV === 'development' ? '.next-dev' : '.next',
    reactStrictMode: true,
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
    }
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
        }
    })
};
