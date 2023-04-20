import ManageWorkspaceLayout from '@app/components/layout/manage-workspace';

export default function ManageLinks() {
    return <ManageWorkspaceLayout></ManageWorkspaceLayout>;
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
