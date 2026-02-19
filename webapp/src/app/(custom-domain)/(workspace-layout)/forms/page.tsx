'use client';

import React from 'react';
import WorkspaceFormsTabContent from '@Components/dashboard/workspace-forms-tab-content';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import ReduxWrapperAppRouter from '@app/containers/ReduxWrapperAppRouter'; // Need redux wrapper if layout doesn't provide it? 
// Actually app/layout.tsx provides ReduxWrapperAppRouter usually. Let's assume it's provided.
// But we need to dispatch workspace to store?
// app/[workspace_name]/layout sets workspace. 
// CustomDomainLayout gets workspace server-side. It should probably pass it to client wrapper which dispatches it.

// Let's create a Client wrapper for the layout to dispatch workspace.
// Or just pass workspace prop to FormsTabContent?
// FormsTabContent uses selectWorkspace inside. So we need to set it in Redux.

// Wait, ResponderPortalLayoutClient takes workspace as prop, but children components might rely on Redux selectWorkspace.
// We should use a dispatcher component.

import ServerSideWorkspaceDispatcher from '@Components/HOCs/ServerSideWorkspaceDispatcher';

// Wait, the page is server component by default in app dir.
// But here I'm creating client component for page content.
// Wait, layout.tsx is server component. It fetches workspace.
// It should render ServerSideWorkspaceDispatcher.

export default function CustomFormsPage() {
    // This component will be child of layout.
    // The layout has fetched workspace. It should wrap children in dispatcher.
    const workspace = useAppSelector(selectWorkspace); // This relies on Redux state being populated.
    return <WorkspaceFormsTabContent isFormCreator={false} workspace={workspace} />;
}
