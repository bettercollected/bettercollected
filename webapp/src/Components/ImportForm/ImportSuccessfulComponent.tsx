import React, { useCallback, useEffect, useRef, useState } from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';

import { debounce } from 'lodash';

import CopyIcon from '@Components/Common/Icons/Common/Copy';
import GreenCircularCheck from '@Components/Common/Icons/Common/GreenCircularCheck';
import ProLogo from '@Components/Common/Icons/Common/ProLogo';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { CircularProgress } from '@mui/material';
import { AnimatePresence, motion } from 'framer-motion';
import ContentEditable from 'react-contenteditable';
import { toast } from 'react-toastify';

import GoogleFolder from '@app/assets/images/google_folder.png';
import TickIcon from '@app/components/icons/tick-icon';
import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import environments from '@app/configs/environments';
import { localesCommon } from '@app/constants/locales/common';
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

    const { t } = useTranslation();

    const dispatch = useAppDispatch();

    const workspace = useAppSelector(selectWorkspace);

    const [showEditView, setShowEditView] = useState(false);

    const [customSlug, setCustomSlug] = useState('');

    const [isError, setIsError] = useState(false);

    const [patchFormSettings, { isLoading: isSavingSlug }] = usePatchFormSettingsMutation();

    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    const slugRegex = /^(?=.*$)(?![_][-])(?!.*[_][-]{2})[a-zA-Z0-9_-]+(?<![_][-])$/;

    const handleSlugUpdate = useCallback(
        debounce((slug: string) => handleUpdate(slug), 1200),
        []
    );

    useEffect(() => {
        setCustomSlug(form?.settings?.customUrl || '');
    }, [form?.settings?.customUrl]);

    const handleOnchange = (e: any) => {
        setIsError(false);
        const plainText = e?.currentTarget?.textContent.replace(/\s/g, '') || '';
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
        if (form?.settings?.customUrl === customSlug) return;
        handleSlugUpdate(customSlug);
    }, [customSlug]);

    const [_, copyToClipboard] = useCopyToClipboard();

    return (
        <div className="lg:px-12 lg:pt-10 pb-5 px-5 pt-5 lg:w-[867px] flex flex-col items-center w-full">
            <GreenCircularCheck />
            <div className="h3-new mt-2 mb-6"> Form Imported Successfully</div>
            <div className="rounded-lg border-black-300 w-full broder border-[1px] p-6">
                <div className="flex gap-2 items-center w-full border-b borber-b-[1px] pb-4 border-black-300">
                    <Image src={GoogleFolder} width={20} height={28} alt="Google Form" />
                    <span className="text-[#734ABD]">{formTitle || 'Untitled Form'}</span>
                </div>
                <div className="pt-4 pb-8">
                    <div className="h4-new gap-5 flex mb-2">
                        <span>Form Link</span>
                        <SavingIndicator saving={saving} saved={saved} />
                    </div>
                    <div className="flex gap-4 items-center flex-wrap break-words">
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
                                        var range = document.createRange();

                                        // Select the entire content of the editable div
                                        range.selectNodeContents(editableDiv);

                                        // Create a selection object
                                        var selection = window.getSelection();

                                        // Remove any existing selections
                                        selection?.removeAllRanges();

                                        // Add the new range to the selection
                                        selection?.addRange(range);
                                    }}
                                    html={customSlug}
                                    tagName="span"
                                    className="text-black-500 !break-words outline-none underline"
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
                </div>
                <div className="mt-8 flex flex-col items-start">
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
                                        openFullScreenModal('WORKSPACE_SETTINGS', { initialIndex: 1 });
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

function SavingIndicator({ saving, saved }: { saving: boolean; saved: boolean }) {
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
