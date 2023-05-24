module.exports = {
    debug: process.env.NEXT_PUBLIC_NODE_ENV === 'development',
    i18n: {
        defaultLocale: 'en',
        locales: ['en', 'nl', 'np']
    },
    fallbackLng: {
        default: ['en']
    },
    reloadOnPrerender: process.env.NEXT_PUBLIC_NODE_ENV === 'development'
};
