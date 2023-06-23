import WorkspaceHomeContainer from '@app/containers/dashboard/WorkspaceHomeContainer';
import Layout from '@app/layouts/_layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

export default function WorkspacePage({ workspace }: { workspace: WorkspaceDto }) {
    const isCustomDomain = !!workspace.customDomain;
    const isAdmin = useAppSelector(selectIsAdmin);
    return (
        <Layout isCustomDomain={isCustomDomain} isClientDomain={isAdmin} showNavbar={!isCustomDomain} hideMenu={false} className="!p-0 bg-white flex flex-col min-h-screen">
            <WorkspaceHomeContainer isCustomDomain={isCustomDomain} />
        </Layout>
    );
}

export { getServerSidePropsInClientHostWithWorkspaceName as getServerSideProps } from '@app/utils/serverSidePropsUtils';
