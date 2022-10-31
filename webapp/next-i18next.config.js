const path = require('path');
module.exports = {
    debug: process.env.NODE_ENV === 'development',
    i18n: {
        defaultLocale: 'en',
        locales: ['en', 'nl']
    },
    localePath: path.resolve('./src/assets/locales/')
};
