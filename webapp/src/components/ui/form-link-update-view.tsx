import React from 'react';

import { useTranslation } from 'next-i18next';

import CopyIcon from '@Components/Common/Icons/Copy';
import { Tooltip } from '@mui/material';
import { toast } from 'react-toastify';
import useCopyToClipboard from 'react-use/lib/useCopyToClipboard';

import environments from '@app/configs/environments';
import { customize } from '@app/constants/locales/customize';
import { toastMessage } from '@app/constants/locales/toast-message';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { updateWorkspace } from '@app/constants/locales/update-workspace';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

import BetterInput from '../Common/input';
import { useModal } from '../modal-views/context';
import Button from './button';

interface ICurrentLinkUpdate {
    link: string;
    isLinkChangable?: boolean;
}
export default function FormLinkUpdateView({ link, isLinkChangable = false }: ICurrentLinkUpdate) {
    const { openModal } = useModal();
    const [_, copyToClipboard] = useCopyToClipboard();
    const form = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const { t } = useTranslation();
    const isCustomDomain = !!workspace.customDomain;

    const clientHost = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${environments.CLIENT_DOMAIN}/${workspace.workspaceName}/forms`;
    const customDomain = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${workspace.customDomain}/forms`;

    const handleFormLinkChnage = () =>
        openModal('CUSTOMIZE_URL', {
            description: t(customize.link.description),
            form: form,
            url: isCustomDomain ? customDomain : clientHost
        });

    return (
        <div className="flex space-between items-end w-full">
            <div className="flex-1">
                <div className="body6 mb-4 !font-semibold">{t(updateWorkspace.common.currentLink)}</div>
                <div className="flex flex-col md:flex-row gap-4 space-y-4 md:space-y-0 md:items-center space-between">
                    <div className="flex items-center gap-4 max-w-full flex-1">
                        <BetterInput inputProps={{ className: '!py-3' }} className="!mb-0" disabled value={link} />

                        <Tooltip title={t(toolTipConstant.copyLink)}>
                            <CopyIcon
                                className="cursor-pointer"
                                onClick={() => {
                                    copyToClipboard(link);
                                    toast(t(toastMessage.copied).toString(), {
                                        type: 'info'
                                    });
                                }}
                            />
                        </Tooltip>
                    </div>
                    {isLinkChangable && (
                        <div>
                            <Button size="medium" onClick={handleFormLinkChnage}>
                                {t(updateWorkspace.common.change)}
                            </Button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
