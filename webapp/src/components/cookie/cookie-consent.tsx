import { useEffect } from 'react';

import 'vanilla-cookieconsent';

import pluginConfig from './cookie-consent-config';

const CookieConsent = () => {
    useEffect(() => {
        /**
         * useEffect is executed twice (React 18+),
         * make sure the plugin is initialized and executed once
         */
        if (!document.getElementById('cc--main') && !!window && typeof window !== 'undefined') {
            const windowObj: any = window;
            windowObj.CookieConsentApi = window.initCookieConsent();
            windowObj.CookieConsentApi.run(pluginConfig);
        }
    }, []);

    return null;
};

export default CookieConsent;
