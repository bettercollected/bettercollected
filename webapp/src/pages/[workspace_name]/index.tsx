import WorkspaceHomeContainer from '@app/containers/dashboard/WorkspaceHomeContainer';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

export default function WorkspacePage({ workspace }: { workspace: WorkspaceDto }) {
    return <WorkspaceHomeContainer isCustomDomain={false} />;
}

export { getServerSidePropsInClientHostWithWorkspaceName as getServerSideProps } from '@app/utils/serverSidePropsUtils';
