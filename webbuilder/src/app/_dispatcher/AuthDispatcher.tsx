'use client';

import { useEffect } from 'react';

import { initialAuthState, useAuthAtom } from '@app/store/jotai/auth';

const AuthDispatcher = ({
    auth,
    children
}: {
    auth: any;
    children: React.ReactNode;
}) => {
    const { setAuthState } = useAuthAtom();
    useEffect(() => {
        if (auth instanceof Object) {
            setAuthState(auth);
        } else {
            setAuthState(initialAuthState);
        }
    }, [auth]);
    return <>{children}</>;
};

export default AuthDispatcher;
