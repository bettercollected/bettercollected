import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import UpgradePro from '@Components/Common/Icons/UpgradePro';

import { Close } from '@app/components/icons/close';
import { useUpgradeModal } from '@app/components/modal-views/upgrade-modal-context';
import PlanCard from '@app/components/pro-plan/plan-card';
import Button from '@app/components/ui/button';
import ActiveLink from '@app/components/ui/links/active-link';
import Loader from '@app/components/ui/loader';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/buttons';
import { pricingPlan } from '@app/constants/locales/pricingplan';
import { useGetPlansQuery } from '@app/store/plans/api';

export enum Feature {
    collaborator,
    forms,
    customDomain,
    workspace
}

export interface IUpgradeToProModal {
    feature?: Feature;
}

export default function UpgradeToProModal(props: IUpgradeToProModal) {
    const { closeModal } = useUpgradeModal();

    const { data, error, isLoading } = useGetPlansQuery();
    const { t } = useTranslation();
    const [activePlan, setActivePlan] = useState<any>();

    useEffect(() => {
        if (data && Array.isArray(data) && data.length > 0) setActivePlan(data[0]);
    }, [data]);

    return (
        <div className=" p-10 relative w-full h-full flex flex-col items-center justify-center">
            <Close
                className="absolute top-10 right-10"
                height={50}
                width={50}
                onClick={() => {
                    closeModal();
                }}
            />

            <UpgradePro />
            <div className="heading4 mt-6 mb-4">{t(pricingPlan.title)}</div>
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
        </div>
    );
}
