import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import Pro from '@Components/Common/Icons/Pro';

import { Close } from '@app/components/icons/close';
import { useUpgradeModal } from '@app/components/modal-views/upgrade-modal-context';
import PlanCard from '@app/components/pro-plan/plan-card';
import Button from '@app/components/ui/button';
import ActiveLink from '@app/components/ui/links/active-link';
import Loader from '@app/components/ui/loader';
import Logo from '@app/components/ui/logo';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/buttons';
import { pricingPlan } from '@app/constants/locales/pricingplan';
import { useGetPlansQuery } from '@app/store/plans/api';

export interface IUpgradeToProModal {
    featureText?: string;
}

export default function UpgradeToProModal({ featureText = 'Upgrade To PRO Plan For More Features' }: IUpgradeToProModal) {
    const { closeModal } = useUpgradeModal();

    const { data, error, isLoading } = useGetPlansQuery();
    const { t } = useTranslation();
    const [activePlan, setActivePlan] = useState<any>();

    useEffect(() => {
        if (data && Array.isArray(data) && data.length > 0) setActivePlan(data[0]);
    }, [data]);

    const features = [
        {
            title: 'Unlimited Form Import',
            description: 'Pro accounts offer unlimited form import, while Free accounts are limited to 100 form imports. This can be a great benefit for businesses that need to import large amounts of data from forms.',
            color: '#FFE9CA'
        },
        {
            title: 'Custom Domain Name',
            description:
                'Pro accounts offer custom domain support, while Free accounts do not. This means that Pro users can use their own domain name for their Workspace, instead of using the “BetterCollected” domain. This can be a great way to make your business look more professional and to improve your brand recognition.',
            color: '#D3E6FE'
        },
        {
            title: 'Multiple Workspace',
            description: 'Pro accounts offer the ability to create multiple workspaces, while Free accounts only allow for one workspace. This means that Pro users can create separate workspaces for different projects, or teams.',
            color: '#E3E0FF'
        },
        {
            title: 'Collaborate With Others',
            description:
                'Pro accounts offer collaboration features, while Basic accounts do not. This means that Pro users can collaborate with others to import forms and manage forms. This can be a great way to get work done faster and more efficiently.',
            color: '#D9FFD6'
        }
    ];

    return (
        <div className="relative h-full overflow-auto pt-20 ">
            <Close
                className="absolute cursor-pointer text-black-600 top-10 right-10"
                height={40}
                width={40}
                onClick={() => {
                    closeModal();
                }}
            />
            <div className="container p-10  w-full h-full mx-auto flex flex-col items-center justify-center">
                <div className="flex  pb-10 items-center">
                    <Logo />
                    <div className="flex items-center rounded ml-1 gap-[2px] h-5 sm:h-6 p-1 sm:p-[6px] text-[10px] sm:body5 uppercase !leading-none !font-semibold !text-white bg-brand-500">
                        <Pro width={12} height={12} />
                        <span className="leading-none">Pro</span>
                    </div>
                </div>

                <div className="text-[36px] text-black-900 font-semibold text-center mb-4 max-w-[370px]">{featureText}</div>
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

                <div className="text-[24px] font-medium mt-20 mb-15">PRO Plan Includes</div>
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
        </div>
    );
}
