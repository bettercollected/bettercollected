import React from 'react';

import {useTranslation} from 'next-i18next';
import AppButton from '@Components/Common/Input/Button/AppButton';

import ProPlanHoc from '@app/Components/HOCs/pro-plan-hoc';
import {buttonConstant} from '@app/constants/locales/button';
import {Features} from '@app/constants/locales/feature';
import {pricingPlan} from '@app/constants/locales/pricingplan';
import {ProLogo} from './logo';

export default function UpgradeToPro() {
    const { t } = useTranslation();
    return (
        <div className="!mt-8">
            <div className="flex items-center ">
                <span className="mr-1 font-semibold">{t(pricingPlan.title)}</span>
                {t(pricingPlan.forThisFeature)}
                <ProPlanHoc hideChildrenIfPro={false} feature={Features.customDomain}>
                    <AppButton className={'ml-2'}>{t(buttonConstant.upgrade)}</AppButton>
                </ProPlanHoc>
            </div>
            <div className="absolute !right-5 !top-2">
                <ProLogo />
            </div>
        </div>
    );
}
