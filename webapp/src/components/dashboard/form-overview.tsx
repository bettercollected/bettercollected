import React from 'react';

import { useRouter } from 'next/router';

import { toast } from 'react-toastify';

import { useGetWorkspaceFormsQuery, useLazyGetWorkspaceFormsQuery } from '@app/store/workspaces/api';

import FormRenderer from '../form-renderer/FormRenderer';
import FullScreenLoader from '../ui/fullscreen-loader';
import EmptyFormsView from './empty-form';

export const FormTabContent = ({ workspaceId, form }: any) => {
    const router = useRouter();

    const formId = router.query.form_id;

    const query = {
        workspace_id: workspaceId,
        form_id: formId
    };

    // const { isLoading, data, isError, error } = useGetWorkspaceFormsQuery(query);

    // if (isLoading) return <FullScreenLoader />;

    // if (isError || !data) return <></>;

    // const formFields = data?.payload.content || [];

    return <div className="w-full">{form.length === 0 ? <EmptyFormsView /> : <FormRenderer form={form} />}</div>;
};
