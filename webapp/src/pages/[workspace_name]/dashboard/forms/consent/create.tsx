import React from 'react';

import BackButtonMenuBar from '@Components/Common/BackButtonMenuBar';
import ConsentInformationPanel from '@Components/Consent/ConsentInformationPanel';
import CreateConsentForm from '@Components/Consent/Form/CreateConsentForm';

import Layout from '@app/layouts/_layout';

export default function CreateConsent() {
    return (
        <Layout isCustomDomain={false} isClientDomain={false} showNavbar={true} hideMenu={false} showAuthAccount={true} className="!p-0 !bg-white flex flex-col !min-h-calc-68">
            <div className="flex min-w-screen">
                <div>
                    <BackButtonMenuBar text="Back to Form" />
                    <CreateConsentForm className="mt-20 pb-20" />
                </div>
                <ConsentInformationPanel />
            </div>
        </Layout>
    );
}
