import { useEffect } from 'react';

import { useRouter } from 'next/router';

import FormBuilderMenuBar from '@Components/FormBuilder/MenuBar';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import environments from '@app/configs/environments';
import FormBuilder from '@app/containers/FormBuilder';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { resetForm, selectCreateForm } from '@app/store/form-builder/slice';
import { FormFieldState, FormState } from '@app/store/form-builder/types';
import { useAppSelector } from '@app/store/hooks';
import { useCreateFormMutation } from '@app/store/workspaces/api';

interface ICreateFormProps {
    workspace: WorkspaceDto;
    _nextI18Next: any;
}

export default function CreateFormPage({ workspace, _nextI18Next }: ICreateFormProps) {
    const createForm: FormState = useAppSelector(selectCreateForm);
    const dispatch = useDispatch();

    const [postCreateForm] = useCreateFormMutation();

    const router = useRouter();

    useEffect(() => {
        dispatch(resetForm());
    }, []);

    const onInsert = () => {};

    const onAddNewPage = () => {};

    const onAddFormLogo = () => {};

    const onAddFormCover = () => {};

    const onPreview = () => {};

    const onFormPublish = async () => {
        console.log(createForm);

        const postRequest: any = {};
        postRequest.title = createForm.title;
        postRequest.description = createForm.description;
        let fields: any = Object.values(createForm.fields);
        fields = fields.map((field: FormFieldState) => {
            if (field.properties?.choices) {
                return { ...field, properties: { ...field.properties, choices: Object.values(field.properties?.choices) } };
            }
            return field;
        });
        postRequest.fields = fields;
        const response: any = await postCreateForm({ workspaceId: workspace.id, body: postRequest });
        if (response?.data) {
            toast('Form created!!', { type: 'success' });
            await router.push(`/${workspace?.workspaceName}/dashboard`);
        } else {
            toast('Error creating form', { type: 'error' });
        }
    };

    return environments.ENABLE_FORM_BUILDER ? (
        <DashboardLayout sidebarClassName="!px-0" dashboardContentClassName="!py-0 w-full h-full bg-white">
            <FormBuilderMenuBar onInsert={onInsert} onAddNewPage={onAddNewPage} onAddFormLogo={onAddFormLogo} onAddFormCover={onAddFormCover} onPreview={onPreview} onFormPublish={onFormPublish} />
            <FormBuilder formId="dummyId" />
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
