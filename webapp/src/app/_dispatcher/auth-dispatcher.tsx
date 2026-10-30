'use client';

import { useEffect } from 'react';

import { resetIfUserChanged } from '@app/store/actions/reset-after-sign-out';
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
        const next = auth instanceof Object ? auth : initialAuthState;
        // signed out on the server (or someone else signed in) while this
        // browser still holds the last user's data: forget it first
        dispatch(resetIfUserChanged(next?.id));
        dispatch(setAuth(next));
    }, [auth]);
    return <>{children}</>;
};

export default AuthDispatcher;
