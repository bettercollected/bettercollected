import React from 'react';

import environments from '@app/configs/environments';

class ChatwootWidget extends React.Component {
    componentDidMount() {
        // Add Chatwoot Settings
        // @ts-ignore
        window.chatwootSettings = {
            hideMessageBubble: false,
            position: 'right', // This can be left or right
            locale: 'en', // Language to be set
            type: 'standard' // [standard, expanded_bubble]
        };

        // Paste the script from inbox settings except the <script> tag
        (function (d, t) {
            let BASE_URL = environments.CHATWOOT_DEPLOY_URL;
            let g: any = d.createElement(t),
                s: any = d.getElementsByTagName(t)[0];
            g.src = BASE_URL + '/packs/js/sdk.js';
            s.parentNode.insertBefore(g, s);
            g.async = !0;
            g.onload = function () {
                // @ts-ignore
                window.chatwootSDK.run({
                    websiteToken: environments.CHATWOOT_WEBSITE_TOKEN,
                    baseUrl: BASE_URL
                });
            };
        })(document, 'script');
    }

    render() {
        return null;
    }
}

export default ChatwootWidget;
