import { useEffect } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import CreateForm from '@Components/CreateForm';
import { Button } from '@mui/material';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import environments from '@app/configs/environments';
import { breadcrumbsItems } from '@app/constants/locales/breadcrumbs-items';
import { formConstant } from '@app/constants/locales/form';
import FormBuilder from '@app/containers/FormBuilder';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { BreadcrumbsItem } from '@app/models/props/breadcrumbs-item';
import { resetForm, selectCreateForm } from '@app/store/create-form/slice';
import { FormFieldState, FormState } from '@app/store/create-form/types';
import { useAppSelector } from '@app/store/hooks';
import { useCreateFormMutation } from '@app/store/workspaces/api';

interface ICreateFormProps {
    workspace: WorkspaceDto;
    _nextI18Next: any;
}

export default function CreateFormPage({ workspace, _nextI18Next }: ICreateFormProps) {
    const createForm: FormState = useAppSelector(selectCreateForm);
    const { t } = useTranslation();
    const dispatch = useDispatch();

    const [postCreateForm] = useCreateFormMutation();
    const locale = _nextI18Next.initialLocale === 'en' ? '' : `${_nextI18Next.initialLocale}/`;
    const router = useRouter();
    const breadcrumbsItem: Array<BreadcrumbsItem> = [
        {
            title: t(breadcrumbsItems.dashboard),
            url: `/${locale}${workspace?.workspaceName}/dashboard`
        },
        {
            title: t(formConstant.default),
            disabled: false
        },
        {
            title: 'Create Form',
            disabled: false
        }
    ];

    useEffect(() => {
        dispatch(resetForm());
    }, []);

    const onSave = async () => {
        const postRequest: any = {};
        postRequest.title = createForm.title;
        postRequest.description = createForm.description;
        postRequest.fields = Object.values(createForm.fields);
        const response: any = await postCreateForm({ workspaceId: workspace.id, body: postRequest });
        if (response?.data) {
            toast('Form created!!', { type: 'success' });
            await router.push(`/${locale}${workspace?.workspaceName}/dashboard`);
        } else {
            toast('Error creating form', { type: 'error' });
        }
    };

    return environments.ENABLE_COMMAND_FORM_BUILDERS ? (
        <DashboardLayout sidebarClassName="!px-0" dashboardContentClassName="!py-0 w-full h-full">
            <FormBuilder formData={{}} formId="dummyId" />
        </DashboardLayout>
    ) : (
        <DashboardLayout>
            <BreadcrumbsRenderer items={breadcrumbsItem} />
            <div className="w-full flex justify-end lg:max-w-[800px]">
                <Button variant="outlined" onClick={onSave}>
                    Save
                </Button>
            </div>
            <CreateForm />
        </DashboardLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
