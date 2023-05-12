const path = require('path');
module.exports = {
    debug: true,
    i18n: {
        defaultLocale: 'en',
        locales: ['en', 'nl', 'np']
    },
    reloadOnPrerender: process.env.NODE_ENV === 'production' ? false : true,
    localePath: path.resolve('./src/assets/locales/')
};
