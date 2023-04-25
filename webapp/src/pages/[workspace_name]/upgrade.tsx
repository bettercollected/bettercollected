import React from 'react';

import AuthNavbar from '@app/components/auth/navbar';
import Button from '@app/components/ui/button';
import ActiveLink from '@app/components/ui/links/active-link';
import environments from '@app/configs/environments';
import { useGetPlansQuery } from '@app/store/plans/api';

export default function Upgrade() {
    const { data, error, isLoading } = useGetPlansQuery();
    return (
        <div className="w-screen mt-[68px]">
            <AuthNavbar showHamburgerIcon={false} showPlans={false} />
            <div className="min-h-calc-68 w-full flex flex-col space-y-5 items-center justify-center">
                {data &&
                    Array.isArray(data) &&
                    data.map((plan: any) => (
                        <div key={plan.price_id}>
                            <ActiveLink href={`${environments.API_ENDPOINT_HOST}/stripe/session/create/checkout?price_id=${plan.price_id}`} referrerPolicy="no-referrer">
                                {plan.price}
                            </ActiveLink>
                        </div>
                    ))}
                Upgrade to pro plan to get this feature
            </div>
        </div>
    );
}

export { getServerSidePropsForWorkspaceAdmin as getServerSideProps } from '@app/lib/serverSideProps';
