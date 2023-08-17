import React from 'react';

import { useTranslation } from 'next-i18next';

import Pro from '@Components/Common/Icons/Pro';

import ProPlanHoc from '@app/components/hoc/pro-plan-hoc';
import Button from '@app/components/ui/button';
import { buttonConstant } from '@app/constants/locales/button';
import { Features } from '@app/constants/locales/feature';
import { pricingPlan } from '@app/constants/locales/pricingplan';

export default function UpgradeToPro() {
    const { t } = useTranslation();
    return (
        <div className="!mt-8">
            <div className="flex items-center ">
                <span className="mr-1 font-semibold">{t(pricingPlan.title)}</span>
                {t(pricingPlan.forThisFeature)}
                <ProPlanHoc hideChildrenIfPro={false} feature={Features.customDomain}>
                    <Button className="ml-4">{t(buttonConstant.upgrade)}</Button>
                </ProPlanHoc>
            </div>
            <div className="absolute !top-2 !right-5">
                <div className="flex items-center rounded h-5 sm:h-6 p-1 sm:p-[6px] text-[10px] sm:body5 uppercase !leading-none !font-semibold !text-white bg-brand-500">
                    <Pro width={12} height={12} />
                    <span className="leading-none">Pro</span>
                </div>
            </div>
        </div>
    );
}
