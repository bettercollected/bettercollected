import React from 'react';

import { useTranslation } from 'next-i18next';
import { serverSideTranslations } from 'next-i18next/serverSideTranslations';
import { NextSeo } from 'next-seo';

import { pricingPlan } from '@app/constants/locales/pricingplan';
import UpgradeToProContainer from '@app/containers/upgrade-to-pro';

const PricingPlan = () => {
    const { t } = useTranslation();
    return (
        <>
            <NextSeo title={t(pricingPlan.pageTitle)} noindex={false} nofollow={false} />
            <div className="relative h-full overflow-auto !bg-white ">
                <UpgradeToProContainer isModal={false} />;
            </div>
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
