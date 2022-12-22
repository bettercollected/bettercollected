import React, { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import environments from '@app/configs/environments';

import FormRenderer from '../form-renderer/FormRenderer';

export const FormTabContent = () => {
    const router = useRouter();

    const formId = router.query.workspace_name;

    const [questions, setQuestions] = useState([]);

    useEffect(() => {
        fetch(`${environments.API_ENDPOINT_HOST}/forms/${formId}`, {
            credentials: 'include',
            headers: {
                'Access-Control-Allow-origin': environments.API_ENDPOINT_HOST
            }
        }).then((data) => {
            data.json().then((d) => {
                console.log('data: ', d);
                setQuestions(d?.payload?.content ?? []);
            });
        });
    }, [router.asPath]);

    return <div className="w-full">{questions.length == 0 ? <></> : <FormRenderer form={questions} />}</div>;
};
