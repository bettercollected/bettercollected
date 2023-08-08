import WorkspaceHomeContainer from '@app/containers/dashboard/WorkspaceHomeContainer';
import Layout from '@app/layouts/_layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

export default function WorkspacePage({ workspace }: { workspace: WorkspaceDto }) {
    const isAdmin = useAppSelector(selectIsAdmin);
    return (
        <Layout isCustomDomain={false} isClientDomain={isAdmin} showNavbar={true} hideMenu={false} className="!p-0 bg-white flex flex-col min-h-screen">
            <WorkspaceHomeContainer isCustomDomain={false} />
        </Layout>
    );
}

export { getServerSidePropsInClientHostWithWorkspaceName as getServerSideProps } from '@app/utils/serverSidePropsUtils';
