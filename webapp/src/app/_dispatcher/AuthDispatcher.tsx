'use client';

import { useEffect } from 'react';

import { initialAuthState, useAuthAtom } from '@app/store/jotai/auth';
import { useAppDispatch } from '@app/store/hooks';
import { setAuth } from '@app/store/auth/slice';

const AuthDispatcher = ({
    auth,
    children
}: {
    auth: any;
    children: React.ReactNode;
}) => {
    const dispatch = useAppDispatch()
    const { setAuthState } = useAuthAtom();
    useEffect(() => {
        if (auth instanceof Object) {
            setAuthState(auth);
            dispatch(setAuth(auth));
        } else {
            setAuthState(initialAuthState);
        }
    }, [auth]);
    return <>{children}</>;
};

export default AuthDispatcher;
