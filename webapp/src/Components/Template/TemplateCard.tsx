import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';
import { useRouter } from 'next/router';

import EditIcon from '@Components/Common/Icons/Edit';
import EllipsisOption from '@Components/Common/Icons/EllipsisOption';
import SettingsIcon from '@Components/Common/Icons/Settings';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { ListItemIcon, MenuItem } from '@mui/material';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
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
    const fullScreenModal = useFullScreenModal();
    const handleClickCard = () => {
        router.push(`/${workspace.workspaceName}/templates/${template.id}`);
    };

    const handleClickEditCard = () => {
        router.push(`/${workspace.workspaceName}/templates/${template.id}/edit`);
    };

    return (
        <div className={'flex flex-col gap-2 '}>
            <div className={'h-[192px] w-[186px] cursor-pointer relative border-black-200 border overflow-hidden rounded hover:shadow-hover'} onClick={handleClickCard}>
                <Image alt={template.title} src={template.previewImage || '/images/no_preview.png'} layout={'fill'} />
            </div>
            <div className="w-full flex justify-between items-start">
                <div className="flex flex-col gap-[5px]">
                    <span className={'h5-new font-semibold max-w-[150px] truncate text-black-800'}>{template.title || t('UNTITLED')}</span>
                    {!isPredefinedTemplate && (
                        <h1 className={'text-xs font-normal text-black-600'}>
                            {t('TEMPLATE.CREATED')}: <span className={'text-black-800'}>{template?.importedFrom ? template.importedFrom : t('TEMPLATE.DEFAULT')}</span>
                        </h1>
                    )}
                </div>
                {!isPredefinedTemplate && (
                    <MenuDropdown
                        width={180}
                        showExpandMore={false}
                        id="template-options"
                        menuTitle={''}
                        showIconBtnEffect
                        PaperProps={{
                            sx: {
                                boxShadow: '0px 0px 12px 0px rgba(7, 100, 235, 0.45)'
                            }
                        }}
                        menuContent={
                            <div>
                                <EllipsisOption />
                            </div>
                        }
                    >
                        <MenuItem onClick={handleClickEditCard} className="body4">
                            <ListItemIcon>
                                <EditIcon width={20} height={20} className="text-black-600" strokeWidth={2} />
                            </ListItemIcon>
                            <span>{t('BUTTON.EDIT')}</span>
                        </MenuItem>
                        <MenuItem
                            onClick={() =>
                                fullScreenModal.openModal('TEMPLATE_SETTINGS_FULL_MODAL_VIEW', {
                                    template,
                                    showTitle: true
                                })
                            }
                            // sx={{ paddingX: '20px', paddingY: '10px', height: '36px' }}
                            className="body4"
                        >
                            <ListItemIcon>
                                <SettingsIcon width={20} height={20} className="text-black-600" strokeWidth={2} />
                            </ListItemIcon>
                            <span>{t('SETTINGS')}</span>
                        </MenuItem>
                    </MenuDropdown>
                )}
            </div>
        </div>
    );
};
export default TemplateCard;
