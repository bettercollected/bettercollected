import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Divider from '@Components/Common/DataDisplay/Divider';
import CopyIcon from '@Components/Common/Icons/Copy';
import LockIcon from '@Components/Common/Icons/lock';
import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { FormControlLabel, Radio, RadioGroup } from '@mui/material';
import { toast } from 'react-toastify';
import useCopyToClipboard from 'react-use/lib/useCopyToClipboard';

import Globe from '@app/components/icons/flags/globe';
import { useModal } from '@app/components/modal-views/context';
import environments from '@app/configs/environments';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { toastMessage } from '@app/constants/locales/toast-message';
import { IFormTemplateDto } from '@app/models/dtos/template';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteTemplateMutation, usePatchTemplateSettingsMutation } from '@app/store/template/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

const TemplateSettings = ({ template }: { template: IFormTemplateDto }) => {
    const { t } = useTranslation();
    const router = useRouter();
    const [templateVisibility, setTemplateVisibility] = useState(template?.settings?.isPublic ? 'Public' : 'Private');
    const { openModal } = useModal();
    const workspace = useAppSelector(selectWorkspace);
    const adminHost = `${environments.ADMIN_DOMAIN.includes('localhost') ? 'http' : 'https'}://${environments.ADMIN_DOMAIN}/templates/${template.id}`;

    const [updateTemplateSettings] = usePatchTemplateSettingsMutation();
    const [deleteTemplate] = useDeleteTemplateMutation();

    const patchSettings = async (isPublic: boolean) => {
        const request = {
            workspace_id: workspace?.id,
            template_id: template?.id,
            body: {
                isPublic: isPublic
            }
        };
        const response: any = await updateTemplateSettings(request);
        if (response?.data) {
            toast(t(localesCommon.updated).toString(), { type: 'success' });
            setTemplateVisibility(response?.data?.settings?.isPublic ? 'Public' : 'Private');
        } else {
            toast('Error Occurred').toString(), { type: 'error' };
        }
    };

    const handleVisibilityChange = (visibility: string) => {
        let visibilityType;
        if (visibility == 'Public') visibilityType = 'Public';
        else visibilityType = 'Private';

        openModal('VISIBILITY_CONFIRMATION_MODAL_VIEW', {
            visibilityType,
            handleOnConfirm: () => {
                patchSettings(visibility == 'Public');
            },
            isTemplate: true
        });
    };

    const handleDeleteTemplate = async () => {
        try {
            const response: any = await deleteTemplate({
                workspace_id: workspace?.id,
                template_id: template?.id
            });
            if (response?.data) {
                toast('Deleted Successfully', { type: 'success' });
                router.replace(`/${workspace.workspaceName}/dashboard/templates`);
            } else {
                toast('Error Occurred').toString(), { type: 'error' };
            }
        } catch (err) {
            toast('Error Occurred').toString(), { type: 'error' };
        }
    };

    return (
        <div className={'flex flex-col gap-4'}>
            <div className={'flex flex-col gap-2'}>
                <h1 className={'text-2xl font-semibold text-black-800'}>Settings</h1>
                <p className={'text-sm font-normal text-black-700'}>Modify template visibility to either public or private, or delete the template.</p>
            </div>
            <div className={'pt-[56px] pb-12 flex flex-col w-3/4'}>
                <h1 className={'text-base font-medium text-black-800 pb-4'}>Template Visibility</h1>
                <RadioGroup className="flex flex-col gap-4" value={templateVisibility}>
                    <Divider />
                    <div className="flex flex-col">
                        <FormControlLabel
                            value="Public"
                            control={<Radio />}
                            onChange={() => handleVisibilityChange('Public')}
                            label={
                                <div className="flex body6 !text-black-800 items-center gap-[6px]">
                                    <Globe className="h-[18px] w-[18px]" />
                                    {t(formConstant.settings.visibility.public)}
                                </div>
                            }
                        />
                        <span className=" body4 !text-black-700">Everyone with the link can use this template. You can share this template.</span>
                        {templateVisibility == 'Public' && <ShareLinkOptions adminHost={adminHost} />}
                    </div>
                    <Divider />
                    <div className="flex flex-col">
                        <FormControlLabel
                            value="Private"
                            control={<Radio />}
                            onChange={() => handleVisibilityChange('Private')}
                            label={
                                <div className="flex body6 !text-black-800 items-center gap-[6px]">
                                    <LockIcon className="h-[18px] w-[18px]" />
                                    {t(formConstant.settings.visibility.private)}
                                </div>
                            }
                        />
                        <span className="body4 !text-black-700">Only your organization can use this template. You cannot share this template.</span>
                    </div>
                    <Divider />
                </RadioGroup>
            </div>
            <div className={'flex flex-col gap-4 w-3/4'}>
                <h1 className={'text-base font-medium text-black-800 pb-4'}>Delete Template</h1>
                <Divider />
                <p className={'text-sm font-normal text-black-700'}>Once you delete a template, it will be permanently removed, and no one with the link will be able to access it.</p>
                <AppButton className={'md: w-[140px]'} variant={ButtonVariant.Danger} onClick={() => openModal('DELETE_TEMPLATE_CONFIRMATION_MODAL_VIEW', { handleDelete: handleDeleteTemplate })}>
                    Delete Template
                </AppButton>
                <Divider />
            </div>
        </div>
    );
};

export default TemplateSettings;

const ShareLinkOptions = ({ adminHost }: { adminHost: string }) => {
    const [_, copyToClipboard] = useCopyToClipboard();
    const { t } = useTranslation();

    const handleOnCopy = () => {
        copyToClipboard(adminHost);
        toast(t(toastMessage.copied).toString(), {
            type: 'info'
        });
    };
    return (
        <div onClick={handleOnCopy} className={'cursor-pointer'}>
            <AppTextField isDisabled className={'mt-4 mb-2 w-3/4'} value={adminHost} />
            <AppButton variant={ButtonVariant.Secondary} icon={<CopyIcon />} onClick={handleOnCopy}>
                Copy Link
            </AppButton>
        </div>
    );
};
