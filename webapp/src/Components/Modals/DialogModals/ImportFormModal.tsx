import { useEffect, useState } from 'react';


import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import ImportFormLoading from '@Components/ImportForm/ImportFormLoading';
import ImportSuccessfulComponent from '@Components/ImportForm/ImportSuccessfulComponent';
import useDrivePicker from '@fyelci/react-google-drive-picker';
import { toast } from 'react-toastify';

import ImportErrorView from '@app/components/form-integrations/import-error-view';
import { useModal } from '@app/components/modal-views/context';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { StandardFormDto } from '@app/models/dtos/form';
import { initFormState } from '@app/store/forms/slice';

import useWorkspace from '@app/store/jotai/workspace';
import { useImportFormMutation, useLazyGetSingleFormFromProviderQuery, useVerifyFormTokenMutation } from '@app/store/redux/importApi';
import { fireworks } from '@app/utils/confetti';
import { getEditFormURL } from '@app/utils/urlUtils';
import { useRouter } from 'next/navigation';

export default function ImportFormModal() {
    const router = useRouter();
    const { closeModal } = useModal();

    const { workspace } = useWorkspace();

    const [verifyToken, { isLoading, data, error }] = useVerifyFormTokenMutation();

    const [openPicker] = useDrivePicker();

    const [form, setForm] = useState<StandardFormDto>(initFormState);
    const [formTitle, setFormTitle] = useState('');

    const [importForm, importFormResult] = useImportFormMutation();
    const [singleFormFromProviderTrigger, singleFormFromProviderResult] = useLazyGetSingleFormFromProviderQuery();

    useEffect(() => {
        verifyToken({ provider: 'google' });
    }, []);

    const handleImportForm = async (formId: string) => {
        const singleForm: any = await singleFormFromProviderTrigger({ provider: 'google', formId: formId });
        const form: any = { ...singleForm?.data, provider: 'google' };
        delete form['clientFormItems'];
        if (singleForm.error) {
            toast.success('Error fetching form');
            return;
            closeModal();
        }
        const response: any = await importForm({
            body: { form, response_data_owner: '' },
            provider: 'google',
            workspaceId: workspace.id
        });
        if (response.error) {
            toast.error('Something went wrong!!');
            closeModal();
        }
        if (response.data) {
            toast.success('Form Imported Successfully');
            setForm(response.data);
            fireworks();
        }
    };

    const customViews: any = [];

    // @ts-ignore
    if (window.google && window.google?.picker) {
        // @ts-ignore
        const customView = new window.google.picker.DocsView(google.picker.ViewId.FORMS);
        // @ts-ignore
        customView?.setMode(window.google.picker.DocsViewMode.LIST);

        customViews.push(customView);
    }
    const openGoogleFilePicker = () => {
        openPicker({
            // @ts-ignore
            clientId: window.PUBLIC_CONFIG?.GOOGLE_CLIENT_ID,
            // @ts-ignore
            developerKey: window.PUBLIC_CONFIG?.GOOGLE_PICKER_API_KEY,
            // viewId: 'FORMS',
            token: data,
            disableDefaultView: true,
            customViews: customViews,
            customScopes: ['https://www.googleapis.com/auth/drive.file'],
            callbackFunction: (data) => {
                if (data.action === 'picked' && data.docs && Array.isArray(data.docs) && data.docs.length > 0) {
                    const formId = data.docs[0].id;
                    const formTitle = data.docs[0].name;
                    setFormTitle(formTitle);
                    handleImportForm(formId);
                } else if (data.action === 'cancel') {
                    closeModal();
                }
            }
        });
    };

    useEffect(() => {
        if (data) {
            openGoogleFilePicker();
        }
    }, [data]);

    useEffect(() => {
        if (form?.formId) {
            router.push(getEditFormURL(workspace, form));
        }
    }, [form]);

    if (isLoading) return <FullScreenLoader />;

    if (error) return <ImportErrorView provider={'google'} unauthorizedScopes={(error as any)?.data?.unauthorizedScopes} />;

    return (
        <div className="start relative flex   w-full  flex-col items-center rounded-md bg-white">
            {formTitle && !form?.formId && <ImportFormLoading loadingText={singleFormFromProviderResult.isLoading ? 'Fetching Form' : 'Importing'} formTitle={formTitle} />}
            {!form?.formId && !formTitle && (
                <AppButton
                    variant={ButtonVariant.Primary}
                    size={ButtonSize.Big}
                    onClick={() => {
                        openGoogleFilePicker();
                    }}
                >
                    Open Google File Picker
                </AppButton>
            )}
            {form?.formId && <ImportSuccessfulComponent form={form} />}
        </div>
    );
}
