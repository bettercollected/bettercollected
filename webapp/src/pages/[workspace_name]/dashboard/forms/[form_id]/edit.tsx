import { useEffect } from 'react';

import { useDispatch } from 'react-redux';

import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import environments from '@app/configs/environments';
import FormBuilder from '@app/containers/FormBuilder';
import { getServerSidePropsForDashboardFormPage } from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { resetForm, setEditForm } from '@app/store/form-builder/slice';

export default function EditFromPage(props: any) {
    const {
        form,
        workspace,
        _nextI18Next
    }: {
        form: StandardFormDto;
        workspace: WorkspaceDto;
        _nextI18Next: any;
    } = props;
    const dispatch = useDispatch();

    useEffect(() => {
        return () => {
            dispatch(resetForm());
        };
    }, []);

    useEffect(() => {
        dispatch(setEditForm(form));
    }, [form]);

    return (
        <DashboardLayout sidebarClassName="!px-0" dashboardContentClassName="!py-0 w-full h-full bg-white">
            <FormBuilder workspace={workspace} _nextI18Next={_nextI18Next} isEditMode />
        </DashboardLayout>
    );
}

export async function getServerSideProps(_context: any) {
    if (!environments.ENABLE_FORM_BUILDER)
        return {
            notFound: true
        };
    const globalProps = await getServerSidePropsForDashboardFormPage(_context);
    if (globalProps?.props?.form?.settings?.provider !== 'self') {
        return {
            notFound: true
        };
    }

    return {
        ...globalProps
    };
}
