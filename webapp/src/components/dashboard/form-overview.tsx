import React, { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import environments from '@app/configs/environments';

import FormRenderer from '../form-renderer/FormRenderer';

export const FormTabContent = ({ workspaceId }: String) => {
    const router = useRouter();

    const formId = router.query.form_id;

    const [questions, setQuestions] = useState([]);

    useEffect(() => {
        if (!!workspaceId && !!formId) {
            fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${workspaceId}/forms?form_id=${formId}`, {
                credentials: 'include',
                headers: {
                    'Access-Control-Allow-origin': environments.API_ENDPOINT_HOST
                }
            }).then((data) => {
                data.json().then((d) => {
                    setQuestions(d?.payload?.content ?? []);
                });
            });
        }
    }, [workspaceId, formId]);

    return <div className="w-full">{questions.length == 0 ? <></> : <FormRenderer form={questions} />}</div>;
};
