"use client";

import AddWorkspaceDomainForm from '@Components/custom-domain/add-workspace-domain-form';
import WorkspaceDomainStatus from '@Components/custom-domain/workspace-domain-status';
import { ProLogo } from '@app/components/ui/logo';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export const CustomDomainCard = () => {
    const workspace = useAppSelector(selectWorkspace);
    return (
        <div className="flex flex-col">
            <div className="text-black-900  flex gap-2 text-sm font-semibold ">
                {' '}
                Custom Domain <ProLogo />
            </div>
            <hr className="text-black-200 mt-2" />
            {!workspace?.customDomain && <AddWorkspaceDomainForm />}
            {workspace?.customDomain && <WorkspaceDomainStatus />}
        </div>
    );
};

export default function CustomDomainClient() {
    return (
        <div className=" rounded-2xl bg-white p-8">
            <CustomDomainCard />
        </div>
    );
}
