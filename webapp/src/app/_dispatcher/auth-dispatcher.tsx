'use client';

import { useEffect } from 'react';

import { initialAuthState, setAuth } from '@app/store/auth/slice';
import { useAppDispatch } from '@app/store/hooks';

const AuthDispatcher = ({
    auth,
    children
}: {
    auth: any;
    children: React.ReactNode;
}) => {
    const dispatch = useAppDispatch()

    useEffect(() => {
        if (auth instanceof Object) {
            dispatch(setAuth(auth));
        } else {
            dispatch(setAuth(initialAuthState));
        }
    }, [auth]);
    return <>{children}</>;
};

export default AuthDispatcher;
