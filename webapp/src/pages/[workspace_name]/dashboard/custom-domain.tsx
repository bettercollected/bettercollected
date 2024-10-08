import AddWorkspaceDomainForm from '@Components/CustomDomain/AddWorkspaceDomainForm';
import WorkspaceDomainStatus from '@Components/CustomDomain/WorkspaceDomainStatus';
import DashboardLayout from '@app/Components/sidebar/dashboard-layout';
import { ProLogo } from '@app/Components/ui/logo';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function CustomDomainSettings() {
    return (
        <>
            <DashboardLayout boxClassName="px-5 pt-10 lg:px-10">
                <div className="max-w-[664px] rounded-2xl bg-white p-8">
                    <CustomDomainCard />
                </div>
            </DashboardLayout>
        </>
    );
}

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

export { getServerSidePropsForWorkspaceAdmin as getServerSideProps } from '@app/lib/serverSideProps';
