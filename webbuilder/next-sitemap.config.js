let siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://www.localhost:3000';

if (process.env.BASE_DEPLOY_PATH) {
    siteUrl = `${siteUrl}${process.env.BASE_DEPLOY_PATH}`;
}

const policy = {
    userAgent: '*'
};

if (process.env.NEXT_PUBLIC_NODE_ENV !== 'production') {
    policy.disallow = '/';
    policy.xRobotsTag = 'noindex, nofollow';
}

/** @type {import('next-sitemap').IConfig} */
module.exports = {
    siteUrl,
    generateRobotsTxt: true,
    robotsTxtOptions: {
        policies: [policy]
    },
    transform: (config, path) => {
        // Ignore /dashboard page, Configure your own pages from here which you don't want to be crawled
        if (path.match(`\\/.*\\/(dashboard)\\.*`)) {
            return null;
        }
        // Use default transformation for all other cases
        return {
            loc: path, // => this will be exported as http(s)://<config.siteUrl>/<path>
            changefreq: config.changefreq,
            priority: config.priority,
            lastmod: config.autoLastmod ? new Date().toISOString() : undefined,
            alternateRefs: config.alternateRefs ?? []
        };
    },
    sourceDir: process.env.NODE_ENV === 'development' ? '.next-dev' : '.next',
    outDir: 'public'
};
