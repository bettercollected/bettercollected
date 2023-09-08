import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import Pro from '@Components/Common/Icons/Pro';

import { Close } from '@app/components/icons/close';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import PlanCard from '@app/components/pro-plan/plan-card';
import Button from '@app/components/ui/button';
import ActiveLink from '@app/components/ui/links/active-link';
import Loader from '@app/components/ui/loader';
import Logo from '@app/components/ui/logo';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { pricingPlan } from '@app/constants/locales/pricingplan';
import { upgradeConst } from '@app/constants/locales/upgrade';
import { useGetPlansQuery } from '@app/store/plans/api';

export interface IUpgradeToProModal {
    featureText?: string;
}

export default function UpgradeToProContainer({ featureText }: IUpgradeToProModal) {
    const { data, isLoading } = useGetPlansQuery();
    const { t } = useTranslation();
    const [activePlan, setActivePlan] = useState<any>();

    useEffect(() => {
        if (data && Array.isArray(data) && data.length > 0) setActivePlan(data[0]);
    }, [data]);

    const features = [
        {
            title: t(upgradeConst.features.unlimitedForms.title),
            description: t(upgradeConst.features.unlimitedForms.description),
            color: '#FFE9CA'
        },
        {
            title: t(upgradeConst.features.customDomain.title),
            description: t(upgradeConst.features.customDomain.description),
            color: '#D3E6FE'
        },
        {
            title: t(upgradeConst.features.collaborator.title),
            description: t(upgradeConst.features.collaborator.description),
            color: '#E3E0FF'
        },
        {
            title: t(upgradeConst.features.workspace.title),
            description: t(upgradeConst.features.workspace.description),
            color: '#D9FFD6'
        }
    ];

    return (
        <div className="container p-10  w-full h-full mx-auto flex flex-col items-center justify-center">
            <div className="flex  pb-10 items-center">
                <Logo />
                <div className="flex items-center rounded ml-1 gap-[2px] h-5 sm:h-6 p-1 sm:p-[6px] text-[10px] sm:body5 uppercase !leading-none !font-semibold !text-white bg-brand-500">
                    <Pro width={12} height={12} />
                    <span className="leading-none">Pro</span>
                </div>
            </div>

            <div className="text-[36px] text-black-900 font-semibold text-center mb-4 max-w-[370px]">{featureText || t(upgradeConst.features.default.slogan)}</div>
            <div className="paragraph text-center mb-6 text-black-600">{t(pricingPlan.description)}</div>
            {isLoading && <Loader variant="blink" />}

            {data &&
                Array.isArray(data) &&
                data.map((plan: any) => (
                    <PlanCard
                        activePlan={activePlan}
                        plan={plan}
                        key={plan.price_id}
                        onClick={() => {
                            setActivePlan(plan);
                        }}
                    />
                ))}

            {data && (
                <ActiveLink className="mt-10" href={`${environments.API_ENDPOINT_HOST}/stripe/session/create/checkout?price_id=${activePlan?.price_id}`}>
                    <Button size="medium">{t(buttonConstant.continue)}</Button>
                </ActiveLink>
            )}

            <div className="text-[24px] font-medium mt-20 mb-15">{t(upgradeConst.proIncludes)}</div>
            <div className="grid grid-cols-1 md:grid-cols-2 w-full gap-6 mt-14">
                {features.map((feature: any, idx: number) => {
                    return (
                        <div key={feature.title + idx} style={{ background: feature.color }} className={`flex rounded p-6 flex-col`}>
                            <div className="flex items-center mb-5">
                                <Pro />
                                <div className="sh1 ml-2 font-semibold ">{feature.title}</div>
                            </div>
                            <div className="">{feature.description}</div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
