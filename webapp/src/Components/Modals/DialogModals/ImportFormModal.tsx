import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';

import CopyIcon from '@Components/Common/Icons/Common/Copy';
import EditIcon from '@Components/Common/Icons/Common/Edit';
import GreenCircularCheck from '@Components/Common/Icons/Common/GreenCircularCheck';
import ProLogo from '@Components/Common/Icons/Common/ProLogo';
import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import useDrivePicker from '@fyelci/react-google-drive-picker';
import { CircularProgress } from '@mui/material';
import confetti from 'canvas-confetti';
import { toast } from 'react-toastify';

import GoogleFolder from '@app/assets/images/google_folder.png';
import ImportErrorView from '@app/components/form-integrations/import-error-view';
import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import environments from '@app/configs/environments';
import { localesCommon } from '@app/constants/locales/common';
import { toastMessage } from '@app/constants/locales/toast-message';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { StandardFormDto } from '@app/models/dtos/form';
import { initFormState, setFormSettings } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useImportFormMutation, useLazyGetSingleFormFromProviderQuery, usePatchFormSettingsMutation, useVerifyFormTokenMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function ImportFormModal() {
    const { closeModal } = useModal();

    const workspace = useAppSelector(selectWorkspace);
    const { t } = useTranslation();

    const [showEditView, setShowEditView] = useState(false);

    const [verifyToken, { isLoading, data, error }] = useVerifyFormTokenMutation();

    const [openPicker] = useDrivePicker();

    const [form, setForm] = useState<StandardFormDto | undefined>();

    const [formId, setFormId] = useState('');
    const [formTitle, setFormTitle] = useState('');

    const [customSlug, setCustomSlug] = useState('');

    const [isError, setIsError] = useState(false);

    const [patchFormSettings, { isLoading: isSavingSlug }] = usePatchFormSettingsMutation();

    const [importForm, importFormResult] = useImportFormMutation();
    const [singleFormFromProviderTrigger, singleFormFromProviderResult] = useLazyGetSingleFormFromProviderQuery();

    const [_, copyToClipboard] = useCopyToClipboard();

    useEffect(() => {
        verifyToken({ provider: 'google' });
    }, []);

    useEffect(() => {
        setCustomSlug(form?.settings?.customUrl || '');
    }, [form?.formId]);

    const slugRegex = /^(?=.*$)(?![_][-])(?!.*[_][-]{2})[a-zA-Z0-9_-]+(?<![_][-])$/;

    const handleOnchange = (e: any) => {
        setIsError(false);
        const customSlug = e.target.value.trim();
        setCustomSlug(customSlug);
        if (!customSlug.match(slugRegex)) {
            setIsError(true);
        }
    };

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
            setForm(response.data);
            fireworks();
        }
    };

    const handleUpdate = async (event: any) => {
        event.preventDefault();
        const body = {
            customUrl: customSlug
        };
        if (customSlug.match(slugRegex)) {
            const response: any = await patchFormSettings({
                workspaceId: workspace.id,
                formId: formId,
                body: body
            });
            if (response.data) {
                const settings: any = response.data.settings;
                // @ts-ignore
                setForm({ ...form, settings: settings });
                toast(t(localesCommon.updated).toString(), { type: 'success' });
                setShowEditView(false);
            } else {
                toast(t(toastMessage.formSettingUpdateError).toString(), { type: 'error' });
                return response.error;
            }
        }
    };

    const openGoogleFilePicker = () => {
        openPicker({
            clientId: environments.GOOGLE_CLIENT_ID,
            developerKey: environments.GOOGLE_PICKER_API_KEY,
            viewId: 'FORMS',
            token: data,
            customScopes: ['https://www.googleapis.com/auth/drive.file'],
            callbackFunction: (data) => {
                console.log('Callback Data', data);
                if (data.action === 'picked' && data.docs && Array.isArray(data.docs) && data.docs.length > 0) {
                    const formId = data.docs[0].id;
                    const formTitle = data.docs[0].name;
                    setFormId(formId);
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
        <div className="bg-white w-full relative  min-h-[480px] md:min-h-[480px] md:w-[777px] lg:w-[1052px] lg:h-[650px] rounded-md p-10 flex flex-col items-center start">
            {!singleFormFromProviderResult?.isLoading && !importFormResult.isLoading && (
                <Close
                    className="absolute p-1 w-6 h-6 hover:bg-gray-100 top-2 right-2"
                    onClick={() => {
                        closeModal();
                    }}
                />
            )}
            {formId && !form && (
                <div className="flex flex-col h-full justify-center items-center">
                    <Image className={'pb-1'} src={GoogleFolder} alt={'GoogleFolder'} />
                    <div className=" h3-new mt-4">
                        {singleFormFromProviderResult?.isLoading && 'Fetching Form'}
                        {importFormResult?.isLoading && 'Importing Form'}
                    </div>
                    <div className=" mt-2">{formTitle}</div>
                    <CircularProgress size={48} className="mt-12" />
                </div>
            )}
            {!formId && (
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
            {form && (
                <div className="lg:px-12 lg:pt-10 lg:pb-5 px-5 pt-5  flex flex-col items-center w-full">
                    <GreenCircularCheck />
                    <div className="h3-new mt-2 mb-6"> Form Imported Successfully</div>
                    <div className="rounded-lg border-black-300 w-full broder border-[1px] p-6">
                        <div className="flex gap-2 items-center w-full border-b borber-b-[1px] pb-4 border-black-300">
                            <Image src={GoogleFolder} width={20} height={28} alt="Google Form" />
                            <span className="text-[#734ABD]">{formTitle || 'Untitled Form'}</span>
                        </div>
                        <div className="pt-4 pb-8">
                            <div className="h4-new mb-2">Form Link</div>
                            {showEditView ? (
                                <div className="flex gap-4 ">
                                    <span className="truncate mt-3  max-w-full">
                                        {environments.HTTP_SCHEME}
                                        {environments.CLIENT_DOMAIN}/{workspace.workspaceName}/
                                    </span>
                                    <div>
                                        <AppTextField placeholder="custom-text" onChange={handleOnchange} value={customSlug} />
                                        <span className="mt-2 text-black-700 text-sm">Avoid space. Only “-” and “_” is accepted.</span>
                                    </div>
                                    <AppButton variant={ButtonVariant.Secondary} className="min-w-[120px]" size={ButtonSize.Medium} onClick={handleUpdate} isLoading={isSavingSlug}>
                                        Save
                                    </AppButton>
                                </div>
                            ) : (
                                <div className="flex flex-col lg:flex-row gap-4 items-center">
                                    <span className="truncate max-w-full">
                                        {environments.HTTP_SCHEME}
                                        {environments.CLIENT_DOMAIN}/{workspace.workspaceName}/forms/<span className="text-pink-500 truncate">{customSlug}</span>
                                    </span>
                                    <div className="flex items-start w-full lg:w-min gap-4">
                                        <AppButton
                                            variant={ButtonVariant.Ghost}
                                            icon={<CopyIcon />}
                                            onClick={() => {
                                                copyToClipboard(`${environments.HTTP_SCHEME}
                                    ${environments.CLIENT_DOMAIN}/${workspace.workspaceName}/forms/${form?.settings?.customUrl}`);
                                                toast('Copied', { type: 'info' });
                                            }}
                                        >
                                            Copy
                                        </AppButton>
                                        <AppButton
                                            variant={ButtonVariant.Ghost}
                                            icon={<EditIcon />}
                                            onClick={() => {
                                                setShowEditView(true);
                                            }}
                                        >
                                            Customize
                                        </AppButton>
                                    </div>
                                </div>
                            )}
                        </div>
                        <div className="mt-10 flex flex-col items-start">
                            <div className="h4-new mb-2 flex gap-2 items-center">
                                Custom Domain Link <ProLogo />
                            </div>
                            {(!workspace.isPro || !workspace?.customDomain) && (
                                <div className="p2-new text-black-700 flex items-center gap-4">
                                    Improve your brand recognition by using custom domain.
                                    {!workspace?.isPro ? <AppButton variant={ButtonVariant.Ghost}>Upgrade to Pro</AppButton> : <AppButton variant={ButtonVariant.Ghost}>Add Custom Domain</AppButton>}
                                </div>
                            )}
                            {workspace?.isPro && workspace?.customDomain && (
                                <div className="flex flex-col lg:flex-row max-w-full gap-4 lg:items-center">
                                    <div className="max-w-full truncate">
                                        <span className="truncate">
                                            {environments.HTTP_SCHEME}
                                            <span className="text-pink-500">{workspace?.customDomain}</span>
                                            /forms/{customSlug}
                                        </span>
                                    </div>
                                    <div>
                                        {!showEditView && (
                                            <AppButton
                                                variant={ButtonVariant.Ghost}
                                                icon={<CopyIcon />}
                                                onClick={() => {
                                                    copyToClipboard(`${environments.HTTP_SCHEME}
                                        ${workspace?.customDomain}/forms/${form?.settings?.customUrl}`);
                                                    toast('Copied', { type: 'info' });
                                                }}
                                            >
                                                Copy
                                            </AppButton>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                    <div className="flex w-full justify-end">
                        <AppButton
                            className="w-[200px] mt-6"
                            size={ButtonSize.Medium}
                            onClick={() => {
                                closeModal();
                            }}
                        >
                            Done
                        </AppButton>
                    </div>
                </div>
            )}
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
