import { useEffect } from 'react';

import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';


function SetClarityUserId() {
    const auth = useAppSelector(selectAuth);

    useEffect(() => {
        // @ts-ignore
        if (auth.id && window.clarity) {
            const script = document.createElement('script');
            script.setAttribute('type', 'text/javascript');
            script.setAttribute('id', 'microsoft-clarity-user-id-script');
            script.setAttribute('defer', '');
            let code = `
                window.clarity('set', 'user_id', '${auth.id}');
                window.clarity("identify", "${auth.id}");
            `;
            script.appendChild(document.createTextNode(code));
            document.body.appendChild(script);
        }
        // @ts-ignore
    }, [auth, window.clarity]);
    return <></>;
}

export default SetClarityUserId;