const path = require('path');
module.exports = {
    debug: false,
    i18n: {
        defaultLocale: 'en',
        locales: ['en', 'nl', 'np']
    },
    localePath: path.resolve('./src/assets/locales/')
};
