import React from 'react';
import ResponderLoginPage from '@Components/Login/ResponderLoginPage';
import LoginLayout from '@Components/Login/login-layout';
import environments from '@app/configs/environments';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

interface LoginComponentProps {
    type?: string;
    workspaceId?: string;
    redirectTo?: string;
    isAdminDomain?: boolean;
}

const LoginComponent: React.FC<LoginComponentProps> = ({ type = 'creator', workspaceId, redirectTo, isAdminDomain }) => {
    if (!isAdminDomain && workspaceId && redirectTo) {
        return <ResponderLoginPage workspaceId={workspaceId} redirectTo={redirectTo} />;
    }

    return <LoginLayout isCreator={type !== 'responder'} workspaceId={workspaceId} />;
};

export default LoginComponent;
