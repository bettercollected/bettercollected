import WorkspaceHomeContainer from '@app/containers/dashboard/WorkspaceHomeContainer';

export default function WorkspacePage({ workspace }: { workspace: any }) {
    return <WorkspaceHomeContainer workspace={workspace} isCustomDomain={false} />;
}

export { getServerSidePropsInClientHostWithWorkspaceName as getServerSideProps } from '@app/utils/serverSidePropsUtils';
