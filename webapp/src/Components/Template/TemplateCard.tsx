import React from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';
import { useRouter } from 'next/router';

import DeleteIcon from '@Components/Common/Icons/Delete';
import EllipsisOption from '@Components/Common/Icons/EllipsisOption';
import AppButton from '@Components/Common/Input/Button/AppButton';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { ListItemIcon, MenuItem } from '@mui/material';

import { useModal } from '@app/components/modal-views/context';
import { formConstant } from '@app/constants/locales/form';
import { IFormTemplateDto } from '@app/models/dtos/template';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface ITemplateCardProps {
    template: IFormTemplateDto;
    isPredefinedTemplate: boolean;
}

const TemplateCard = ({ template, isPredefinedTemplate }: ITemplateCardProps) => {
    const router = useRouter();
    const workspace = useAppSelector(selectWorkspace);

    const { t } = useTranslation();

    const { openModal } = useModal();
    const handleClickCard = () => {
        router.push(`/${workspace.workspaceName}/templates/${template.id}`);
    };

    return (
        <div className={'flex flex-col gap-2 '}>
            <div className={'h-[192px] w-[186px] cursor-pointer relative border-black-200 border rounded'} onClick={handleClickCard}>
                <Image alt={template.title} src={''} layout={'fill'} />
            </div>
            <div className="w-full flex justify-between items-center">
                <span className={'h5-new font-semibold max-w-[150px] truncate text-black-800'}>{template.title}</span>
                {!isPredefinedTemplate && (
                    <MenuDropdown width={220} showExpandMore={false} id="template-options" menuTitle={''} menuContent={<EllipsisOption />}>
                        <MenuItem onClick={() => openModal('DELETE_TEMPLATE_CONFIRMATION_MODAL_VIEW', { template })} sx={{ paddingX: '20px', paddingY: '10px', height: '36px' }} className="body4">
                            <ListItemIcon>
                                <DeleteIcon width={20} height={20} className="text-black-800" strokeWidth={1} />
                            </ListItemIcon>
                            <span>{t('TEMPLATE.DELETE_TEMPLATE')}</span>
                        </MenuItem>
                    </MenuDropdown>
                )}
            </div>
            {!isPredefinedTemplate && (
                <h1 className={'text-xs font-normal text-black-600'}>
                    Created: <span className={'text-black-800'}>{template?.importedFrom ? template.importedFrom : 'Default'}</span>
                </h1>
            )}
        </div>
    );
};

export default TemplateCard;
