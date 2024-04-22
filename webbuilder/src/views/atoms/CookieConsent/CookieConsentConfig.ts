import { CookieConsentConfig } from 'vanilla-cookieconsent';

/**
 * @type {UserConfig}
 */
const pluginConfig: CookieConsentConfig = {
    guiOptions: {
        consentModal: {
            layout: 'box',
            position: 'bottom right',
            equalWeightButtons: true,
            flipButtons: false
        },
        preferencesModal: {
            layout: 'box',
            position: 'left',
            equalWeightButtons: true,
            flipButtons: false
        }
    },

    // onFirstAction: function (user_preferences: any, cookie: any) {
    //     // callback triggered only once
    //     const windowObj: any = window;
    //     const analyticsEnabled =
    //         windowObj.CookieConsentApi.allowedCategory('analytics');
    //     // console.log(`analytics ${analyticsEnabled ? 'enabled' : 'disabled'}`);
    // },

    categories: {
        necessary: {
            readOnly: true,
            enabled: true
        },
        analytics: {
            autoClear: {
                cookies: [
                    {
                        name: /^(_ga|_gid)/
                    }
                ]
            }
        }
    },

    language: {
        default: 'en',
        translations: {
            en: {
                consentModal: {
                    title: 'We use cookies!',
                    description:
                        'Hi, this website uses essential cookies to ensure its proper operation and tracking cookies to understand how you interact with it. The latter will be set only after consent. <button type="button" data-cc="c-settings" class="cc-link">Let me choose</button>',
                    acceptAllBtn: 'Accept all',
                    acceptNecessaryBtn: 'Reject all',
                    showPreferencesBtn: 'Manage preferences'
                },
                preferencesModal: {
                    title: 'Cookie Settings',
                    savePreferencesBtn: 'Save settings',
                    acceptAllBtn: 'Accept all',
                    acceptNecessaryBtn: 'Reject all',
                    closeIconLabel: 'Close',
                    sections: [
                        {
                            title: 'Cookie usage 📢',
                            description:
                                'I use cookies to ensure the basic functionalities of the website and to enhance your online experience. You can choose for each category to opt-in/out whenever you want. For more details relative to cookies and other sensitive data, please read the full <a target="_blank" href="https://bettercollected.com/privacy-policy" class="cc-link">privacy policy</a>.'
                        },
                        {
                            title: 'Strictly necessary cookies',
                            description:
                                'These cookies are essential for the proper functioning of my website. Without these cookies, the website would not work properly',
                            linkedCategory: 'necessary'
                        },
                        {
                            title: 'Performance and Analytics cookies',
                            description:
                                'These cookies allow the website to remember the choices you have made in the past',
                            linkedCategory: 'analytics',
                            cookieTable: {
                                headers: {
                                    name: 'Name',
                                    domain: 'Domain',
                                    expiration: 'Expiration',
                                    description: 'Description'
                                },
                                body: [
                                    // list of all expected cookies
                                    {
                                        name: '^_ga', // match all cookies starting with "_ga"
                                        domain: 'google.com',
                                        expiration: '2 years',
                                        description:
                                            'This cookie is used to distinguish users on your website. It calculates visitor, session, and campaign data and keeps track of site usage for the site&apos;s analytics report. It has a default expiration time of two years.'
                                    },
                                    {
                                        name: '_gid',
                                        domain: 'google.com',
                                        expiration: '1 day',
                                        description:
                                            'This cookie is used to distinguish users on your website. It is used to store information on how visitors use a website and helps in creating an analytics report of how the website is doing. The data collected includes the number of visitors, their source, and the pages visited. It has a default expiration time of 24 hours.'
                                    }
                                ]
                            }
                        },
                        {
                            title: 'Advertisement and Targeting cookies',
                            description:
                                'These cookies collect information about how you use the website, which pages you visited and which links you clicked on. All of the data is anonymized and cannot be used to identify you',
                            linkedCategory: 'targeting'
                        },
                        {
                            title: 'More information',
                            description:
                                'For any queries in relation to our policy on cookies and your choices, please <a class="cc-link" target="_blank" href="https://bettercollected.com/contact-us">contact us</a>.'
                        }
                    ]
                }
            }
        }
    }
};

export default pluginConfig;
