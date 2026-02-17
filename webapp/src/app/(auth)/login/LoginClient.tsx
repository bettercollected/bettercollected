'use client';

import React from 'react';
import LoginComponent from '@Components/Login/login-component';
import ReduxWrapperAppRouter from '@app/containers/ReduxWrapperAppRouter';
import environments from '@app/configs/environments';

export default function LoginClient() {
    return (
        <ReduxWrapperAppRouter>
            <LoginComponent />
        </ReduxWrapperAppRouter>
    );
}
