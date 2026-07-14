import { useEffect, useState } from 'react';

import { useTranslation } from 'react-i18next';

import HeaderModalWrapper from '@Components/modals/modal-wrapper/header-modal-wrapper';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import { useModal } from '@app/components/modal-views/context';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { placeHolder } from '@app/constants/locales/placeholder';
import { toastMessage } from '@app/constants/locales/toast-message';
import { AppInput } from '@app/shadcn/components/ui/input';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { selectWorkspace, setWorkspace } from '@app/store/workspaces/slice';


export default function UpdateCustomDomainModal() {
    const { toast } = useToast();
    const workspace = useAppSelector(selectWorkspace);
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();

    const dispatch = useAppDispatch();
    const { t } = useTranslation();
    const [error, setError] = useState(false);

    const [updateText, setUpdateText] = useState(workspace.customDomain || '');

    const { closeModal } = useModal();

    useEffect(() => {
        setTimeout(() => {

            setError(!!updateText && !updateText.match('(([a-zA-Z]{1})|([a-zA-Z]{1}[a-zA-Z]{1})|([a-zA-Z]{1}[0-9]{1})|([0-9]{1}[a-zA-Z]{1})|([a-zA-Z0-9][a-zA-Z0-9-_]{1,61}[a-zA-Z0-9]))\\.([a-zA-Z]{2,6}|[a-zA-Z0-9-]{2,30}\\.[a-zA-Z]{2,3})'));
        }, 0);
    }, [updateText]);

    const handleSubmit = async (event: any) => {
        event.preventDefault();
        if (error || !updateText) return;
        if (updateText === workspace.customDomain) {
            closeModal();
            return;
        }
        const formData = new FormData();
        formData.append('custom_domain', updateText);
        const body = {
            workspace_id: workspace.id,
            body: formData
        };
        const response: any = await patchExistingWorkspace(body);
        if (response.data) {
            dispatch(setWorkspace(response.data));
            toast({ description: t(toastMessage.customDomainUpdated).toString() });
            closeModal();
        } else if (response.error) {
            toast({ description: response.error.data?.message || response.error.data || t(toastMessage.somethingWentWrong), variant: 'destructive' });
        }
    };

    return (
        <HeaderModalWrapper headerTitle="Add Custom Domain">
            <form onSubmit={handleSubmit}>
                <div className="text-start max-w-full mb-4 body4 !text-pink-500">{t('UPGRADE.FEATURES.CUSTOM_DOMAIN.NOTE', { domain: environments.CUSTOM_DOMAIN_IP })}</div>
                <h1 className={'body3 !text-black-800 mb-1'}>{t('UPGRADE.FEATURES.CUSTOM_DOMAIN.TEXT_FIELD_TITLE')}</h1>
                <AppInput
                    placeholder={t(placeHolder.enterCustomDomain)}
                    value={updateText}
                    onChange={(e) => {
                        setUpdateText(e.target.value);
                    }}
                />
                <Button className="w-full mt-4" data-testid="save-button" type="submit" isLoading={isLoading} size="medium" variant="primary">
                    {t(buttonConstant.updateNow)}
                </Button>
            </form>
        </HeaderModalWrapper>
    );
}