import React from 'react';

import { serverSideTranslations } from 'next-i18next/serverSideTranslations';
import { NextSeo } from 'next-seo';
import { useTranslation } from 'next-i18next';

import UpgradeToProModal from '@app/components/modal-views/modals/upgrade-to-pro-modal';
import { pricingPlan } from '@app/constants/locales/pricingplan';

const PricingPlan = () => {
    const {t} = useTranslation()
    return (
        <>
            <NextSeo title={t(pricingPlan.pageTitle)} noindex={false} nofollow={false} />
            <UpgradeToProModal isPage={true} />;
        </>
    );
};

export async function getServerSideProps({ locale, ..._context }: any) {
    return {
        props: {
            ...(await serverSideTranslations(locale, ['common', 'builder'], null, ['en', 'nl']))
        }
    };
}

export default PricingPlan;
