import React, { useCallback, useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';

import { debounce } from 'lodash';

import CircularCheck from '@Components/Common/Icons/Common/CircularCheck';
import CopyIcon from '@Components/Common/Icons/Common/Copy';
import ProLogo from '@Components/Common/Icons/Common/ProLogo';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import { CircularProgress } from '@mui/material';
import { AnimatePresence, motion } from 'framer-motion';
import ContentEditable from 'react-contenteditable';
import { toast } from 'react-toastify';

import GoogleFolder from '@app/assets/images/google_folder.png';
import { Close } from '@app/components/icons/close';
import TickIcon from '@app/components/icons/tick-icon';
import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import environments from '@app/configs/environments';
import { toastMessage } from '@app/constants/locales/toast-message';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { StandardFormDto } from '@app/models/dtos/form';
import { selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function ImportSuccessfulComponent() {
    const form: StandardFormDto = useAppSelector(selectForm);
    const { formId, title: formTitle } = form;
    const { closeModal } = useModal();

    const { openModal: openFullScreenModal } = useFullScreenModal();

    const { openBottomSheetModal } = useBottomSheetModal();

    const { t } = useTranslation();

    const dispatch = useAppDispatch();

    const workspace = useAppSelector(selectWorkspace);

    const [showEditView, setShowEditView] = useState(false);

    const [customSlug, setCustomSlug] = useState(form?.settings?.customUrl || '');

    const [isError, setIsError] = useState(false);

    const [patchFormSettings] = usePatchFormSettingsMutation();

    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    const slugRegex = /^(?![_-])(?!.*[_-]{2})[a-zA-Z0-9_-]+(?![_-])$/;

    const handleSlugUpdate = useCallback(
        debounce((slug: string) => handleUpdate(slug), 1200),
        []
    );

    const handleOnchange = (e: any) => {
        setIsError(false);
        const plainText = e?.currentTarget?.textContent || '';
        if (!plainText.match(slugRegex)) {
            setIsError(true);
        } else {
            setSaving(true);
        }
        setCustomSlug(plainText);
    };
    const handleUpdate = async (customSlug: string) => {
        if (form?.settings?.customUrl === customSlug) return;
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
                dispatch(setForm({ ...form, settings: settings }));
                setSaved(true);
                setSaving(false);
                setTimeout(() => {
                    setSaved(false);
                }, 1500);
            } else {
                toast(t(toastMessage.formSettingUpdateError).toString(), { type: 'error' });
                return response.error;
            }
        }
    };

    useEffect(() => {
        if (form?.settings?.customUrl === customSlug) {
            setSaving(false);
            setSaved(true);
            setTimeout(() => {
                setSaved(false);
            }, 1500);
            return;
        }
        handleSlugUpdate(customSlug);
    }, [customSlug]);

    const [_, copyToClipboard] = useCopyToClipboard();

    return (
        <div className="lg:px-12 lg:pt-10 pb-5 px-5 pt-5 lg:w-[867px] flex flex-col items-center w-full">
            <CircularCheck />
            <div className="h3-new mt-2 mb-6"> Form Imported Successfully</div>
            <div className="rounded-lg border-black-300 w-full broder border-[1px] p-6">
                <div className="flex gap-2 items-center w-full border-b borber-b-[1px] pb-4 border-black-300">
                    <Image src={GoogleFolder} width={20} height={28} alt="Google Form" />
                    <span className="text-[#734ABD]">{formTitle || 'Untitled Form'}</span>
                </div>
                <div className="pt-4 pb-8">
                    <div className="h4-new gap-5 flex mb-2">
                        <span>Form Link</span>
                        <SavingIndicator saving={saving} saved={saved} error={isError} />
                    </div>
                    <div className="flex gap-4 items-start flex-col break-words">
                        <span className="break-words max-w-full">
                            {environments.HTTP_SCHEME}
                            {environments.CLIENT_DOMAIN}/{workspace.workspaceName}/
                            {showEditView ? (
                                <ContentEditable
                                    id="custom-slug-content-editable"
                                    onKeyDown={(event) => {
                                        if (event.key === 'Enter') {
                                            event.preventDefault();
                                            event.stopPropagation();
                                        }
                                    }}
                                    onFocus={(event) => {
                                        const editableDiv = event.target;
                                        let range = document.createRange();

                                        // Select the entire content of the editable div
                                        range.selectNodeContents(editableDiv);

                                        // Create a selection object
                                        let selection = window.getSelection();

                                        // Remove any existing selections
                                        selection?.removeAllRanges();

                                        // Add the new range to the selection
                                        selection?.addRange(range);
                                    }}
                                    html={customSlug}
                                    tagName="span"
                                    className=" focus:text-black-500 active:text-black-500 text-black-800 !break-words outline-none underline"
                                    onChange={handleOnchange}
                                />
                            ) : (
                                <span className="text-pink-500 break-words">{customSlug}</span>
                            )}
                        </span>

                        <AppButton
                            variant={ButtonVariant.Ghost}
                            icon={<CopyIcon />}
                            className="min-w-[120px]"
                            onClick={() => {
                                copyToClipboard(`${environments.HTTP_SCHEME}
                                        ${environments.CLIENT_DOMAIN}/${workspace?.workspaceName}/forms/${customSlug}`);
                                toast('Copied', { type: 'info' });
                            }}
                        >
                            Copy
                        </AppButton>
                    </div>
                    <div className="h-4">{isError && customSlug && <span className="p2-new text-red-500">Avoid using spaces or special characters. Only “-” and “_” is accepted.</span>}</div>
                </div>
                <div className="mt-4 flex flex-col items-start">
                    <div className="h4-new mb-2 flex gap-2 items-center">
                        Custom Domain Link <ProLogo />
                    </div>
                    {(!workspace.isPro || !workspace?.customDomain) && (
                        <div className="p2-new text-black-700 flex items-center gap-4">
                            Improve your brand recognition by using custom domain.
                            {!workspace?.isPro ? (
                                <AppButton
                                    variant={ButtonVariant.Ghost}
                                    onClick={() => {
                                        closeModal();
                                        openFullScreenModal('UPGRADE_TO_PRO');
                                    }}
                                >
                                    Upgrade to Pro
                                </AppButton>
                            ) : (
                                <AppButton
                                    variant={ButtonVariant.Ghost}
                                    onClick={() => {
                                        closeModal();
                                        openBottomSheetModal('WORKSPACE_SETTINGS', { initialIndex: 1 });
                                    }}
                                >
                                    Add Custom Domain
                                </AppButton>
                            )}
                        </div>
                    )}
                    {workspace?.isPro && workspace?.customDomain && (
                        <div className="flex gap-4 items-center flex-wrap">
                            <span className="break-all max-w-full">
                                {environments.HTTP_SCHEME}
                                <span className="text-pink-500 break-words">{workspace?.customDomain}</span>
                                /forms/<span className="break-words">{customSlug}</span>
                            </span>
                            <AppButton
                                variant={ButtonVariant.Ghost}
                                icon={<CopyIcon />}
                                onClick={() => {
                                    copyToClipboard(`${environments.HTTP_SCHEME}
                                        ${workspace?.customDomain}/forms/${customSlug}`);
                                    toast('Copied', { type: 'info' });
                                }}
                            >
                                Copy
                            </AppButton>
                        </div>
                    )}
                </div>
            </div>
            <div className="flex w-full gap-4 mt-6 justify-end">
                {!showEditView && (
                    <AppButton
                        variant={ButtonVariant.Secondary}
                        size={ButtonSize.Medium}
                        onClick={() => {
                            setShowEditView(true);
                            setTimeout(() => {
                                document.getElementById('custom-slug-content-editable')?.focus();
                            }, 200);
                        }}
                    >
                        Customize Form Link
                    </AppButton>
                )}
                <AppButton
                    className="w-[200px]"
                    size={ButtonSize.Medium}
                    onClick={() => {
                        closeModal();
                    }}
                >
                    Done
                </AppButton>
            </div>
        </div>
    );
}

function SavingIndicator({ saving, saved, error }: { saving: boolean; saved: boolean; error: boolean }) {
    if (error) {
        return <Close className="!text-red-500 p-1 " />;
    }
    return (
        <AnimatePresence mode="wait" initial={false}>
            {(saving || saved) && (
                <motion.div
                    initial={{ opacity: 1 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{
                        ease: 'linear',
                        duration: 1.5,
                        x: { duration: 1.5 }
                    }}
                >
                    <span>{saving ? <CircularProgress size={16} /> : saved ? <TickIcon className="text-green-500" /> : <></>}</span>
                </motion.div>
            )}
        </AnimatePresence>
    );
}
