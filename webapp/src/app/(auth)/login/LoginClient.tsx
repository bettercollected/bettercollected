'use client';

import LoginView from '@app/app/(auth)/_components/login-view';
import ReduxWrapperAppRouter from '@app/containers/ReduxWrapperAppRouter';

export default function LoginClient() {
    return (
        <ReduxWrapperAppRouter>
            <LoginView />
        </ReduxWrapperAppRouter>
    );
}
