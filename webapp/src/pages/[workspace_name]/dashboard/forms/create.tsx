import { useEffect } from 'react';

import { useDispatch } from 'react-redux';

import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import environments from '@app/configs/environments';
import FormBuilder from '@app/containers/FormBuilder';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { resetForm } from '@app/store/form-builder/slice';

interface ICreateFormProps {
    workspace: WorkspaceDto;
    _nextI18Next: any;
}

export default function CreateFormPage({ workspace, _nextI18Next }: ICreateFormProps) {
    const dispatch = useDispatch();

    useEffect(() => {
        dispatch(resetForm());
    }, []);

    return environments.ENABLE_FORM_BUILDER ? (
        <DashboardLayout sidebarClassName="!px-0" dashboardContentClassName="!py-0 w-full h-full bg-white">
            <FormBuilder workspace={workspace} _nextI18Next={_nextI18Next} />
        </DashboardLayout>
    ) : (
        <></>
    );
}

export async function getServerSideProps(_context: any) {
    if (!environments.ENABLE_FORM_BUILDER)
        return {
            notFound: true
        };
    const globalProps = await getAuthUserPropsWithWorkspace(_context);
    return {
        props: { ...globalProps.props }
    };
}
