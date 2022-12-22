import React, { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import environments from '@app/configs/environments';

import FormRenderer from '../form-renderer/FormRenderer';

export const FormTabContent = () => {
    const router = useRouter();

    const formId = router.query.workspace_name;

    const [questions, setQuestions] = useState([]);

    useEffect(() => {
        fetch(`${environments.API_ENDPOINT_HOST}/forms/1-CQgKC3Ms-PqCuJNXDEkjlRP1MR4NscStXhz5rhkddk`, {
            credentials: 'include',
            headers: {
                'Access-Control-Allow-origin': environments.API_ENDPOINT_HOST
            }
        }).then((data) => {
            data.json().then((d) => {
                console.log('data: ', d.payload.content.questions);
                setQuestions(d.payload.content);
            });
        });
    }, []);

    return <div className="w-full">{questions.length == 0 ? <></> : <FormRenderer form={questions} />}</div>;
};
