module.exports = {
    debug: false,
    i18n: {
        defaultLocale: 'en',
        locales: ['en', 'nl']
    },
    fallbackLng: {
        default: ['en']
    },
    reloadOnPrerender: process.env.NEXT_PUBLIC_NODE_ENV === 'development'
};
