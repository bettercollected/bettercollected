import { Trans, useTranslation } from 'react-i18next';

import { sso } from '@app/constants/locales/sso';

// The setup guide for people who run their own instance; a workspace admin on a
// hosted instance asks that instance's administrator or support team instead.
export const SSO_SETUP_GUIDE_URL = 'https://github.com/bettercollected/bettercollected/blob/develop/docs/sso.md';

export default function SsoSelfHostingGuide() {
    const { t } = useTranslation();
    return (
        <span className="mt-2 block" data-testid="sso-self-hosting">
            {/* eslint-disable-next-line jsx-a11y/anchor-has-content, jsx-a11y/control-has-associated-label -- Trans fills in the link text */}
            <Trans t={t} i18nKey={sso.SELF_HOSTING} components={{ 1: <a href={SSO_SETUP_GUIDE_URL} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-black-900" /> }} />
        </span>
    );
}
