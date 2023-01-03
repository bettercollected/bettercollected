import React from 'react';

import { useRouter } from 'next/router';

import { toast } from 'react-toastify';

import { useGetWorkspaceFormsQuery, useLazyGetWorkspaceFormsQuery } from '@app/store/workspaces/api';

import FormRenderer from '../form-renderer/FormRenderer';
import FullScreenLoader from '../ui/fullscreen-loader';
import EmptyFormsView from './empty-form';

export const FormTabContent = ({ form }: any) => {
    return (
        <div className="w-full">
            <FormRenderer form={form} />
        </div>
    );
};
