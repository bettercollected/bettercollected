const path = require('path');
module.exports = {
    debug: process.env.NODE_ENV === 'development',
    i18n: {
        defaultLocale: 'en',
        locales: ['en', 'nl', 'np']
    },
    localePath: typeof window === 'undefined' ? require('path').resolve('./public/locales') : '/locales'
};
