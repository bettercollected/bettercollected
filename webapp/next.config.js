// [old page, its tab now] under /<workspace>/dashboard/.
const LEGACY_WORKSPACE_SECTIONS = [
    ['ai-settings', 'ai/settings'],
    ['ai-profile', 'ai/profile'],
    ['ai-memory', 'ai/memory'],
    ['api-keys', 'ai/mcp'],
    ['domains', 'sso/domains']
];

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
        // custom-domain service probes (github.com/sireto/custom-domain)
        return [
            { source: '/.well-known/custom-domain-workspace', destination: '/api/custom-domain/workspace' },
            { source: '/.well-known/custom-domain-origin-verification', destination: '/api/custom-domain/origin-verification' }
        ];
    },
    async redirects() {
        // Workspace settings pages that became tabs of the Single sign-on and
        // AI sections (src/lib/workspace-sections.ts). Permanent, so
        // bookmarks, docs and links in mails keep working; the query string
        // is kept.
        return LEGACY_WORKSPACE_SECTIONS.map(([from, to]) => ({
            source: `/:workspace_name/dashboard/${from}`,
            destination: `/:workspace_name/dashboard/${to}`,
            permanent: true
        }));
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
            // kept after the Typeform integration's removal: forms imported
            // from Typeform may still show images hosted there
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
