import WorkspaceHomeContainer from '@app/containers/dashboard/WorkspaceHomeContainer';
import Layout from '@app/layouts/_layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

export default function WorkspacePage({ workspace }: { workspace: WorkspaceDto }) {
    const isCustomDomain = false;
    return (
        <Layout isCustomDomain={isCustomDomain} isClientDomain showNavbar={!isCustomDomain} hideMenu={!isCustomDomain} className="!p-0 bg-white flex flex-col min-h-screen">
            <WorkspaceHomeContainer isCustomDomain={false} />
        </Layout>
    );
}

export { getServerSidePropsInClientHostWithWorkspaceName as getServerSideProps } from '@app/utils/serverSidePropsUtils';
