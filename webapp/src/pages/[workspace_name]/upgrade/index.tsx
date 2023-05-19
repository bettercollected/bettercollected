import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import UpgradePro from '@Components/Common/Icons/UpgradePro';

import AuthNavbar from '@app/components/auth/navbar';
import PlanCard from '@app/components/pro-plan/plan-card';
import Button from '@app/components/ui/button';
import ActiveLink from '@app/components/ui/links/active-link';
import Loader from '@app/components/ui/loader';
import environments from '@app/configs/environments';
import { buttons } from '@app/constants/locales/buttons';
import { pricingPlan } from '@app/constants/locales/pricingplan';
import { useGetPlansQuery } from '@app/store/plans/api';

export default function Index() {
    const { data, error, isLoading } = useGetPlansQuery();
    const { t } = useTranslation();
    const [activePlan, setActivePlan] = useState<any>();

    useEffect(() => {
        if (data && Array.isArray(data) && data.length > 0) setActivePlan(data[0]);
    }, [data]);

    return (
        <div className="w-full px-5 mt-[68px] mb-10">
            <AuthNavbar showHamburgerIcon={false} showPlans={false} />
            <div className="min-h-calc-68 w-full flex flex-col items-center justify-center">
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
                        <Button size="medium">{t(buttons.continue)}</Button>
                    </ActiveLink>
                )}

                {/* <div className="mt-2 body2 italic text-black ">No risk. Cancel any time.</div> */}
            </div>
        </div>
    );
}

export { getServerSidePropsForWorkspaceAdmin as getServerSideProps } from '@app/lib/serverSideProps';
