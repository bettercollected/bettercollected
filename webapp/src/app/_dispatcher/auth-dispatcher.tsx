'use client';

import { useEffect } from 'react';

import { resetIfUserChanged } from '@app/store/actions/reset-after-sign-out';
import { initialAuthState, setAuth } from '@app/store/auth/slice';
import { useAppDispatch } from '@app/store/hooks';
import { ServerAuthAnswer } from '@app/utils/session-answer';

const AuthDispatcher = ({
    auth,
    children
}: {
    auth: ServerAuthAnswer;
    children: React.ReactNode;
}) => {
    const dispatch = useAppDispatch()

    useEffect(() => {
        if (auth?.kind === 'signed-in') {
            // someone else signed in while this browser still holds the last
            // user's data: forget it first
            dispatch(resetIfUserChanged(auth.user.id));
            dispatch(setAuth(auth.user));
        } else if (auth?.kind === 'signed-out') {
            // the server said nobody is signed in (401): the same
            dispatch(resetIfUserChanged(undefined));
            dispatch(setAuth(initialAuthState));
        }
        // 'unknown' (a server error, the backend out of reach) says nothing
        // about the session: whoever is signed in here stays signed in, with
        // their caches, and the status check asks again
    }, [auth]);
    return <>{children}</>;
};

export default AuthDispatcher;
