import { WorkspaceDto } from './workspaceDto';

export interface IServerSideProps {
    hasCustomDomain: boolean;
    workspaceId: string | null;
    workspace: WorkspaceDto | null;
    [dProps: string]: any;
}
