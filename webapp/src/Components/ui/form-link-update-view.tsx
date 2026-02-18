import React from 'react';

import { useTranslation } from 'next-i18next';

import PrivateFormButtonWrapper from '@Components/Common/FormVisibility/PrivateFormButtonWrapper';
import CopyIcon from '@Components/Common/Icons/Common/Copy';
import AppTextField from '@Components/Common/Input/AppTextField';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import useCopyToClipboard from 'react-use/lib/useCopyToClipboard';

import { useToast } from '@app/shadcn/components/ui/use-toast';
import { Button } from '@app/shadcn/components/ui/button';
import Globe from '@app/Components/icons/flags/globe';
import { useFullScreenModal } from '@app/Components/modal-views/full-screen-modal-context';
import { formPage } from '@app/constants/locales/form-page';
import { toastMessage } from '@app/constants/locales/toast-message';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';


interface ICurrentLinkUpdate {
    isCustomDomain?: boolean;
    link: string;
    isDisable?: boolean;
    isProUser?: boolean;
    isPrivate?: boolean;
}

export default function FormLinkUpdateView({ link, isCustomDomain = false, isDisable = false, isProUser, isPrivate = false }: ICurrentLinkUpdate) {
    const { openModal: openFullScreenModal } = useFullScreenModal();
    const { openBottomSheetModal } = useBottomSheetModal();
    const { toast } = useToast();
    const [_, copyToClipboard] = useCopyToClipboard();
    const workspace = useAppSelector(selectWorkspace);
    const { t } = useTranslation();

    const handleOnClickCustomDomain = () => {
        if (isProUser) {
            openBottomSheetModal('WORKSPACE_SETTINGS', { initialIndex: 1 });
        } else {
            openFullScreenModal('UPGRADE_TO_PRO');
        }
    };

    const handleOnCopy = () => {
        if (isPrivate) return;
        copyToClipboard(link);
        toast({ description: t(toastMessage.copied).toString() });
    };

    return (
        <div className="flex relative space-between items-end w-full">
            <div className="flex-1">
                <div className="body6 mb-2 !font-semibold">{isCustomDomain ? t(formPage.linksCustomDomainLink) : t(formPage.linksDefaultLink)}</div>
                <div className="flex flex-col items-start gap-2 w-full flex-1">
                    <AppTextField isDisabled={true} disabledColor={'#1D1D1D'} className={'w-full'} onClick={handleOnCopy} value={link} />
                    <div className="flex flex-row gap-4 items-center w-full">
                        <PrivateFormButtonWrapper isPrivate={isPrivate}>
                            <Button variant="secondary" disabled={isPrivate} onClick={handleOnCopy}>
                                <CopyIcon className="cursor-pointer mr-2" />
                                {t(formPage.linkCopyLink)}
                            </Button>
                        </PrivateFormButtonWrapper>
                        {(!isProUser || !workspace?.customDomain) && (
                            <Button variant="tertiary" disabled={isDisable} onClick={handleOnClickCustomDomain}>
                                <Globe className="h-[18px] w-[18px] mr-2" />
                                {t(formPage.linksUseCustomDomain)}
                            </Button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}