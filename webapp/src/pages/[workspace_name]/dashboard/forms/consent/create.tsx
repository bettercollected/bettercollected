import React from 'react';

import BackButtonMenuBar from '@Components/Common/BackButtonMenuBar';

import CreateConsentContainer from '@app/containers/consent/CreateConsentContainer';
import Layout from '@app/layouts/_layout';

export default function CreateConsent() {
    return (
        <Layout isCustomDomain={false} isClientDomain={false} showNavbar={true} hideMenu={false} showAuthAccount={true} className="!p-0 !bg-white flex flex-col !min-h-calc-68">
            <BackButtonMenuBar text="Back to Form" />
            <CreateConsentContainer className="mt-20" />
        </Layout>
    );
}
