import { useState } from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import CopyIcon from '@Components/Common/Icons/Common/Copy';
import LockIcon from '@Components/Common/Icons/lock';
import { Button } from '@app/shadcn/components/ui/button';
import { Label } from '@app/shadcn/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@app/shadcn/components/ui/radio-group';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import useCopyToClipboard from 'react-use/lib/useCopyToClipboard';

import Globe from '@app/Components/icons/flags/globe';
import { useModal } from '@app/Components/modal-views/context';
import environments from '@app/configs/environments';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { toastMessage } from '@app/constants/locales/toast-message';
import { IFormTemplateDto } from '@app/models/dtos/template';
import { AppInput } from '@app/shadcn/components/ui/input';
import { useAppSelector } from '@app/store/hooks';
import { usePatchTemplateSettingsMutation } from '@app/store/template/api';
import { selectWorkspace } from '@app/store/workspaces/slice';


const TemplateSettings = ({ template, showTitle }: { template: IFormTemplateDto; showTitle: boolean }) => {
    const { toast } = useToast();
    const { t } = useTranslation();
    const [templateVisibility, setTemplateVisibility] = useState(template?.settings?.isPublic ? 'Public' : 'Private');
    const { openModal } = useModal();
    const workspace = useAppSelector(selectWorkspace);
    const adminHost = `${environments.ADMIN_DOMAIN.includes('localhost') ? 'http' : 'https'}://${environments.ADMIN_DOMAIN}/templates/${template.id}`;

    const [updateTemplateSettings] = usePatchTemplateSettingsMutation();

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
            toast({ description: t(localesCommon.updated).toString() });
            setTemplateVisibility(response?.data?.settings?.isPublic ? 'Public' : 'Private');
        } else {
            toast({ description: 'Error Occurred', variant: 'destructive' });
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

    return (
        <div className={'flex flex-col gap-4'}>
            {showTitle && <h1 className={'text-3xl mb-4 font-semibold text-black-800'}>{template.title}</h1>}
            <div className={'flex flex-col gap-2'}>
                <h1 className={'text-2xl font-semibold text-black-800'}>{t('TEMPLATE.SETTINGS.TITLE')}</h1>
                <p className={'text-sm font-normal text-black-700'}>{t('TEMPLATE.SETTINGS.DESCRIPTION')}</p>
            </div>
            <div className={'pt-[56px] pb-8 flex flex-col md:w-3/4'}>
                <h1 className={'text-base font-medium text-black-800 pb-4'}>{t('TEMPLATE.SETTINGS.VISIBILITY.TEMPLATE_VISIBILITY')}</h1>
                <RadioGroup className="flex flex-col gap-4" value={templateVisibility} onValueChange={(val) => handleVisibilityChange(val)}>
                    <Divider className={'text-black-300'} />
                    <div className="flex flex-col gap-2">
                        <div className="flex items-center space-x-2">
                            <RadioGroupItem value="Public" id="public" />
                            <Label htmlFor="public" className="cursor-pointer">
                                <div className="flex body6 !text-black-800 items-center gap-[6px]">
                                    <Globe className="h-[18px] w-[18px]" />
                                    {t(formConstant.settings.visibility.public)}
                                </div>
                            </Label>
                        </div>
                        <span className=" body4 !text-black-700 ml-6">{t('TEMPLATE.SETTINGS.VISIBILITY.PUBLIC')}</span>
                        {templateVisibility == 'Public' && <ShareLinkOptions adminHost={adminHost} />}
                    </div>
                    <Divider className={'text-black-200'} />
                    <div className="flex flex-col gap-2">
                        <div className="flex items-center space-x-2">
                            <RadioGroupItem value="Private" id="private" />
                            <Label htmlFor="private" className="cursor-pointer">
                                <div className="flex body6 !text-black-800 items-center gap-[6px]">
                                    <LockIcon className="h-[18px] w-[18px]" />
                                    {t(formConstant.settings.visibility.private)}
                                </div>
                            </Label>
                        </div>
                        <span className="body4 !text-black-700 ml-6">{t('TEMPLATE.SETTINGS.VISIBILITY.PRIVATE')}</span>
                    </div>
                    <Divider className={'text-black-200'} />
                </RadioGroup>
            </div>
            <div className={'flex flex-col gap-4 md:w-3/4'}>
                <h1 className={'text-base font-medium text-black-800'}>{t('TEMPLATE.DELETE_TEMPLATE')}</h1>
                <Divider className={'text-black-200'} />

                <p className={'text-sm font-normal text-black-700'}>{t('TEMPLATE.SETTINGS.DELETE_DESCRIPTION')}</p>
                <Button className="w-full md:w-[140px]" variant="danger" onClick={() => openModal('DELETE_TEMPLATE_CONFIRMATION_MODAL_VIEW', { template })}>
                    {t('TEMPLATE.DELETE_TEMPLATE')}
                </Button>
                <Divider className={'text-black-200'} />
            </div>
        </div>
    );
};

export default TemplateSettings;

const ShareLinkOptions = ({ adminHost }: { adminHost: string }) => {
    const { toast } = useToast();
    const [_, copyToClipboard] = useCopyToClipboard();
    const { t } = useTranslation();

    const handleOnCopy = () => {
        copyToClipboard(adminHost);
        toast({ description: t(toastMessage.copied).toString() });
    };
    return (
        <div>
            <div className="cursor-pointer" onClick={handleOnCopy}>
                <AppInput className={'mt-4 mb-2 w-3/4'} disabled value={adminHost} />
            </div>
            <Button variant="secondary" className="gap-2" onClick={handleOnCopy}>
                <CopyIcon />
                {t('TOOLTIP.COPY_LINK')}
            </Button>
        </div>
    );
};