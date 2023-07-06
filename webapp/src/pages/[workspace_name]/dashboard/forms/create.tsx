import { useEffect } from 'react';

import FormBuilderMenuBar from '@Components/FormBuilder/MenuBar';
import { useDispatch } from 'react-redux';

import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import environments from '@app/configs/environments';
import FormBuilder from '@app/containers/FormBuilder';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { resetForm, selectCreateForm } from '@app/store/form-builder/slice';
import { FormState } from '@app/store/form-builder/types';
import { useAppSelector } from '@app/store/hooks';

interface ICreateFormProps {
    workspace: WorkspaceDto;
    _nextI18Next: any;
}

export default function CreateFormPage({ workspace, _nextI18Next }: ICreateFormProps) {
    const createForm: FormState = useAppSelector(selectCreateForm);
    const dispatch = useDispatch();

    useEffect(() => {
        dispatch(resetForm());
    }, []);

    const onInsert = () => {};

    const onAddNewPage = () => {};

    const onAddFormLogo = () => {};

    const onAddFormCover = () => {};

    const onPreview = () => {};

    const onFormPublish = async () => {
        console.log(createForm.fields);
        // const postRequest: any = {};
        // postRequest.title = createForm.title;
        // postRequest.description = createForm.description;
        // postRequest.fields = Object.values(createForm.fields);
        // const response: any = await postCreateForm({ workspaceId: workspace.id, body: postRequest });
        // if (response?.data) {
        //     toast('Form created!!', { type: 'success' });
        //     await router.push(`/${locale}${workspace?.workspaceName}/dashboard`);
        // } else {
        //     toast('Error creating form', { type: 'error' });
        // }
    };

    return environments.ENABLE_FORM_BUILDER ? (
        <DashboardLayout sidebarClassName="!px-0" dashboardContentClassName="!py-0 w-full h-full bg-white">
            <FormBuilderMenuBar onInsert={onInsert} onAddNewPage={onAddNewPage} onAddFormLogo={onAddFormLogo} onAddFormCover={onAddFormCover} onPreview={onPreview} onFormPublish={onFormPublish} />
            <FormBuilder formData={{}} formId="dummyId" />
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
