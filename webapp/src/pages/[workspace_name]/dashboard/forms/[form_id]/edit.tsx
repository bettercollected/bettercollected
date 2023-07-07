import { useEffect } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import environments from '@app/configs/environments';
import FormBuilder from '@app/containers/FormBuilder';
import { getServerSidePropsForDashboardFormPage } from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { resetForm, selectCreateForm, setEditForm } from '@app/store/form-builder/slice';
import { FormFieldState, FormState } from '@app/store/form-builder/types';
import { useAppSelector } from '@app/store/hooks';
import { usePatchFormMutation } from '@app/store/workspaces/api';

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
    const router = useRouter();
    const [patchForm, { isLoading }] = usePatchFormMutation();
    const locale = _nextI18Next.initialLocale === 'en' ? '' : `${_nextI18Next.initialLocale}/`;
    const createForm: FormState = useAppSelector(selectCreateForm);
    const dispatch = useDispatch();
    const { t } = useTranslation();

    useEffect(() => {
        dispatch(setEditForm(form));
    }, [form]);

    useEffect(() => {
        return () => {
            dispatch(resetForm());
        };
    }, []);

    const onFormPublish = async () => {
        const patchRequest: any = {};
        patchRequest.title = createForm.title;
        patchRequest.description = createForm.description;
        let fields: any = Object.values(createForm.fields);
        fields = fields.map((field: FormFieldState) => {
            if (field.properties?.choices) {
                return { ...field, properties: { ...field.properties, choices: Object.values(field.properties?.choices) } };
            }
            return field;
        });
        patchRequest.fields = fields;
        const response: any = await patchForm({ workspaceId: workspace.id, formId: form.formId, body: patchRequest });
        if (response?.data) {
            toast('Form updated', { type: 'success' });
            await router.push(`/${locale}${workspace?.workspaceName}/dashboard/forms/${form.formId}`);
        } else {
            toast('Error updating form', { type: 'error' });
        }
    };

    return (
        <DashboardLayout sidebarClassName="!px-0" dashboardContentClassName="!py-0 w-full h-full bg-white">
            <FormBuilder onFormPublish={onFormPublish} />
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
