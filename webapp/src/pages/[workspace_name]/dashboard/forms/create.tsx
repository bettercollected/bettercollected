import { useEffect } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AddFieldGrid from '@Components/CreateForm/AddFieldGrid';
import FormField from '@Components/CreateForm/FormField';
import FormProperty from '@Components/CreateForm/FormProperty';
import { Button } from '@mui/material';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import { breadcrumbsItems } from '@app/constants/locales/breadcrumbs-items';
import { formConstant } from '@app/constants/locales/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { BreadcrumbsItem } from '@app/models/props/breadcrumbs-item';
import { resetForm, selectCreateForm, setFormDescription, setFormTitle } from '@app/store/create-form/slice';
import { FormFieldState, FormState } from '@app/store/create-form/types';
import { useAppSelector } from '@app/store/hooks';
import { useCreateFormMutation } from '@app/store/workspaces/api';

interface ICreateFormProps {
    workspace: WorkspaceDto;
    _nextI18Next: any;
}

export default function CreateForm({ workspace, _nextI18Next }: ICreateFormProps) {
    const createForm: FormState = useAppSelector(selectCreateForm);
    const { t } = useTranslation();
    const dispatch = useDispatch();

    const [postCreateForm] = useCreateFormMutation();
    const locale = _nextI18Next.initialLocale === 'en' ? '' : `${_nextI18Next.initialLocale}/`;
    const router = useRouter();
    const { openModal } = useFullScreenModal();
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
            title: t(breadcrumbsItems.create),
            disabled: false
        }
    ];

    useEffect(() => {
        dispatch(resetForm);
    }, []);

    const onSave = async () => {
        const postRequest: any = {};
        postRequest.title = createForm.title;
        postRequest.description = createForm.description;
        postRequest.fields = Object.values(createForm.fields);
        console.log(postRequest);

        const response: any = await postCreateForm({ workspaceId: workspace.id, body: postRequest });
        if (response?.data) {
            toast('Form created!!', { type: 'success' });
            await router.push(`/${locale}${workspace?.workspaceName}/dashboard`);
        } else {
            toast('Error creating form', { type: 'error' });
        }
    };

    return (
        <DashboardLayout>
            <BreadcrumbsRenderer items={breadcrumbsItem} />
            <div className="w-full flex justify-end lg:max-w-[800px]">
                <Button variant="outlined" onClick={onSave}>
                    Save
                </Button>
            </div>
            <div className="lg:max-w-[700px]">
                <FormProperty action={setFormTitle} propertyValue={createForm.title} inputProps={{ placeholder: 'Form Title' }} />
                <FormProperty action={setFormDescription} propertyValue={createForm.description} inputProps={{ placeholder: 'Form Description' }} />
                <div className="flex flex-col gap-3">
                    {Object.values(createForm.fields).map((field: FormFieldState) => (
                        <FormField key={field.id} field={field} />
                    ))}
                </div>

                {Object.keys(createForm.fields).length === 0 ? (
                    <>
                        <div>Start your from with</div>
                        <AddFieldGrid />
                    </>
                ) : (
                    <div className="w-full flex justify-center mt-10">
                        <Button
                            onClick={() => {
                                openModal('ADD_FIELD');
                            }}
                        >
                            Add field
                        </Button>
                    </div>
                )}
            </div>
        </DashboardLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
