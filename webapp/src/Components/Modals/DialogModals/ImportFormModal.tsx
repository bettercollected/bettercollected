import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import ImportFormLoading from '@Components/ImportForm/ImportFormLoading';
import ImportSuccessfulComponent from '@Components/ImportForm/ImportSuccessfulComponent';
import useDrivePicker from '@fyelci/react-google-drive-picker';
import confetti from 'canvas-confetti';
import { toast } from 'react-toastify';

import ImportErrorView from '@app/components/form-integrations/import-error-view';
import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import environments from '@app/configs/environments';
import { toastMessage } from '@app/constants/locales/toast-message';
import { resetSingleForm, selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useImportFormMutation, useLazyGetSingleFormFromProviderQuery, useVerifyFormTokenMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function ImportFormModal() {
    const { closeModal } = useModal();

    const workspace = useAppSelector(selectWorkspace);
    const { t } = useTranslation();

    const [verifyToken, { isLoading, data, error }] = useVerifyFormTokenMutation();

    const [openPicker] = useDrivePicker();

    const dispatch = useAppDispatch();

    const form = useAppSelector(selectForm);

    const [formTitle, setFormTitle] = useState('');

    const [importForm, importFormResult] = useImportFormMutation();
    const [singleFormFromProviderTrigger, singleFormFromProviderResult] = useLazyGetSingleFormFromProviderQuery();

    useEffect(() => {
        verifyToken({ provider: 'google' });

        return () => {
            dispatch(resetSingleForm());
        };
    }, []);

    const handleImportForm = async (formId: string) => {
        const singleForm: any = await singleFormFromProviderTrigger({ provider: 'google', formId: formId });
        const form: any = { ...singleForm?.data, provider: 'google' };
        delete form['clientFormItems'];
        if (singleForm.error) {
            toast.success(t(toastMessage.couldNotImportedForm).toString());
            return;
        }
        const response: any = await importForm({
            body: { form, response_data_owner: '' },
            provider: 'google',
            workspaceId: workspace.id
        });
        if (response.data) {
            toast.success(t(toastMessage.formImportedSuccessfully).toString());
            dispatch(setForm(response.data));
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
            clientId: environments.GOOGLE_CLIENT_ID,
            developerKey: environments.GOOGLE_PICKER_API_KEY,
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

    if (isLoading) return <FullScreenLoader />;

    if (error) return <ImportErrorView provider={'google'} />;

    return (
        <div className="bg-white w-full relative   rounded-md  flex flex-col items-center start">
            {!singleFormFromProviderResult?.isLoading && !importFormResult.isLoading && (
                <Close
                    className="absolute p-1 w-6 h-6 hover:bg-gray-100 top-2 right-2"
                    onClick={() => {
                        closeModal();
                    }}
                />
            )}
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
            {form?.formId && <ImportSuccessfulComponent />}
        </div>
    );
}

function fireworks() {
    let duration = 3 * 1000;
    let animationEnd = Date.now() + duration;
    let defaults = { startVelocity: 30, spread: 360, ticks: 60, zIndex: 99999 };

    function randomInRange(min: number, max: number) {
        return Math.random() * (max - min) + min;
    }

    let interval: NodeJS.Timer = setInterval(function () {
        let timeLeft = animationEnd - Date.now();

        if (timeLeft <= 0) {
            return clearInterval(interval);
        }

        let particleCount = 100 * (timeLeft / duration);
        // since particles fall down, start a bit higher than random
        confetti({ ...defaults, particleCount, origin: { x: randomInRange(0.1, 0.3), y: Math.random() - 0.2 } });
        confetti({ ...defaults, particleCount, origin: { x: randomInRange(0.7, 0.9), y: Math.random() - 0.2 } });
    }, 250);
}
