import environments from '@app/configs/environments';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

const predefined_names = ['forms', 'submissions', 'templates'];

export const checkIfPredefinedWorkspaceName = (name: string | null) => {
    return name && predefined_names.includes(name);
};

export const checkErrorForWorkspaceName = (name: string | null) => {
    if (name) {
        return checkIfPredefinedWorkspaceName(name) || !name.match(/^[a-zA-Z0-9_]+$/) || name.includes(' ');
    }
    return true;
};

export function getWorkspaceShareURL(workspace: WorkspaceDto) {
    if (workspace.isPro && workspace.customDomain) {
        return `${environments.HTTP_SCHEME}${workspace.customDomain}`;
    } else {
        return `${environments.HTTP_SCHEME}${environments.CLIENT_DOMAIN}/${workspace.workspaceName}`;
    }
}
