'use client';

import { useEffect } from 'react';

import * as VanillaCookieConsent from 'vanilla-cookieconsent';

import pluginConfig from './CookieConsentConfig';

const CookieConsent = () => {
    useEffect(() => {
        VanillaCookieConsent.run(pluginConfig);
    }, []);

    return null;
};

export default CookieConsent;
