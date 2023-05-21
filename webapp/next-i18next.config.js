const path = require('path');
module.exports = {
    debug: process.env.NODE_ENV === 'development',
    i18n: {
        defaultLocale: 'en',
        locales: ['en', 'nl', 'np']
    },
    reloadOnPrerender: process.env.NODE_ENV === 'development',
    localePath: typeof window === 'undefined' ? require('path').resolve('./src/assets/locales') : '/src/assets/locales'
};
