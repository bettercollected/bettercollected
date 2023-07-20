import { useEffect } from 'react';

import FormBuilderContainerWrapper from '@Components/HOCs/FormBuilderContainerWrapper';

import environments from '@app/configs/environments';
import FormBuilder from '@app/containers/FormBuilder';
import Layout from '@app/layouts/_layout';
import { getServerSidePropsForDashboardFormPage } from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { resetForm, setEditForm } from '@app/store/form-builder/actions';
import { useAppDispatch } from '@app/store/hooks';

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
    const dispatch = useAppDispatch();

    useEffect(() => {
        return () => {
            dispatch(resetForm());
        };
    }, []);

    useEffect(() => {
        dispatch(setEditForm(form));
    }, [form]);

    return (
        <FormBuilderContainerWrapper>
            <Layout isCustomDomain={false} isClientDomain={false} showNavbar={true} hideMenu={false} showAuthAccount={true} className="!p-0 !bg-white flex flex-col !min-h-calc-68">
                <FormBuilder workspace={workspace} _nextI18Next={_nextI18Next} isEditMode />
            </Layout>
        </FormBuilderContainerWrapper>
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
