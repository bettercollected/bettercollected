"use client";

import AddWorkspaceDomainForm from '@Components/CustomDomain/AddWorkspaceDomainForm';
import WorkspaceDomainStatus from '@Components/CustomDomain/WorkspaceDomainStatus';
import { ProLogo } from '@app/Components/ui/logo';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export const CustomDomainCard = () => {
    const workspace = useAppSelector(selectWorkspace);
    return (
        <div className="flex max-w-[664px] flex-col">
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

export default function CustomDomainSettings() {
    return (
        <div className="max-w-[664px] rounded-2xl bg-white p-8">
            <CustomDomainCard />
        </div>
    );
}
