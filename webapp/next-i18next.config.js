const path = require('path');
module.exports = {
    debug: false,
    i18n: {
        defaultLocale: 'en',
        locales: ['en', 'nl']
    },
    localePath: path.resolve('./src/assets/locales/')
};
