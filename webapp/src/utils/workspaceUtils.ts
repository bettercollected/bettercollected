"use client";
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

export function getWorkspaceShareURL(workspace: WorkspaceDto, customDomain: boolean = true) {
    if (workspace.isPro && workspace.customDomain && customDomain) {
        return `${window.PUBLIC_CONFIG?.HTTP_SCHEME}${workspace.customDomain}`;
    } else {
        return `${window.PUBLIC_CONFIG?.HTTP_SCHEME}${window.PUBLIC_CONFIG?.FORM_DOMAIN}/${workspace.workspaceName}`;
    }
}
