import React, { useEffect, useState } from 'react';

import AuthNavbar from '@app/components/auth/navbar';
import PaymentLogo from '@app/components/icons/payment-logo';
import PlanCard from '@app/components/pro-plan/plan-card';
import Button from '@app/components/ui/button';
import ActiveLink from '@app/components/ui/links/active-link';
import Loader from '@app/components/ui/loader';
import environments from '@app/configs/environments';
import { useGetPlansQuery } from '@app/store/plans/api';

export default function Upgrade() {
    const { data, error, isLoading } = useGetPlansQuery();

    const [activePlan, setActivePlan] = useState<any>();

    useEffect(() => {
        if (data && Array.isArray(data) && data.length > 0) setActivePlan(data[0]);
    }, [data]);

    return (
        <div className="w-screen px-5 mt-[68px]">
            <AuthNavbar showHamburgerIcon={false} showPlans={false} />
            <div className="min-h-calc-68 w-full flex flex-col items-center justify-center">
                <PaymentLogo className="mb-8" />
                <div className="heading4 mb-4">PRO Plan</div>
                <div className="paragraph text-center mb-6 text-black-600">
                    Choose a payment plan to upgrade to <strong>PRO</strong>.
                </div>
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
                        <Button size="medium">Continue</Button>
                    </ActiveLink>
                )}
            </div>
        </div>
    );
}

export { getServerSidePropsForWorkspaceAdmin as getServerSideProps } from '@app/lib/serverSideProps';
