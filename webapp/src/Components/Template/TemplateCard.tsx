import React from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';
import { useRouter } from 'next/router';

import EditIcon from '@Components/Common/Icons/Common/Edit';
import EllipsisOption from '@Components/Common/Icons/Common/EllipsisOption';
import SettingsIcon from '@Components/Common/Icons/Common/Settings';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import { CircularProgress, ListItemIcon, MenuItem } from '@mui/material';

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

    const { openBottomSheetModal } = useBottomSheetModal();
    const handleClickCard = () => {
        router.push(`/${workspace.workspaceName}/templates/${template.id}`);
    };

    const handleClickEditCard = () => {
        router.push(`/${workspace.workspaceName}/templates/${template.id}/edit`);
    };

    return (
        <div className={'flex flex-col gap-2 min-w-[150px] w-[150px] md:min-w-[186px] '}>
            <div
                className={`h-[170px]  md:h-[192px] cursor-pointer relative border-black-200 border overflow-hidden rounded hover:shadow-hover ${!template.previewImage && 'flex justify-center items-center bg-gradient-to-b from-blue-400 to-blue-800 '}`}
                onClick={handleClickCard}
            >
                {template?.previewImage ? (
                    <Image alt={template.title} src={template.previewImage} layout={'fill'} />
                ) : (
                    <CircularProgress
                        sx={{
                            color: '#F2F7FF'
                        }}
                        size={24}
                    />
                )}
            </div>
            <div className="w-full flex justify-between items-start">
                <div className="flex flex-col gap-[5px]">
                    <span className={'h5-new font-semibold max-w-[110px] md:max-w-[150px] truncate text-black-800'}>{template.title || t('UNTITLED')}</span>
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
                                openBottomSheetModal('TEMPLATE_SETTINGS_FULL_MODAL_VIEW', {
                                    template,
                                    showTitle: true
                                })
                            }
                            className="body4"
                        >
                            <ListItemIcon>
                                <SettingsIcon width={20} height={20} className="text-black-600" />
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