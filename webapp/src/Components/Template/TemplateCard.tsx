import React from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/legacy/image';
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
import LayoutWrapper from '@app/views/organism/Layout/LayoutWrapper';
import WelcomePage from '@app/views/organism/Form/WelcomePage';

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
        <div className={`flex min-w-[150px] flex-col gap-2 md:min-w-[186px] ${template?.builderVersion !== 'v2' && 'w-[150px]'}`}>
            <div
                className={`border-black-200  hover:shadow-hover relative  cursor-pointer overflow-hidden rounded border md:h-[192px] ${
                    !template.previewImage && template?.builderVersion === 'v2' ? '!h-[157px] w-[281px]' : 'flex h-[170px] items-center justify-center bg-gradient-to-b from-blue-400 to-blue-800 '
                }`}
                onClick={handleClickCard}
            >
                {template?.builderVersion !== 'v2' && (
                    <>
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
                    </>
                )}
                {template?.builderVersion === 'v2' && (
                    <div className="relative h-[157px] w-[281px] overflow-hidden rounded-md">
                        <div className="pointer-events-none h-[810px] w-[1440px] scale-[0.195]" style={{ transformOrigin: 'top left' }}>
                            <LayoutWrapper theme={template?.theme} disabled layout={template.welcomePage?.layout} imageUrl={template?.welcomePage?.imageUrl}>
                                <WelcomePage isPreviewMode theme={template?.theme} welcomePageData={template?.welcomePage} />
                            </LayoutWrapper>
                        </div>
                    </div>
                    // <div className="flex cursor-pointer flex-col rounded-lg border border-transparent p-1 hover:border-pink-500" key={template?.id}>

                    //     <div className="p2-new mt-2 !font-medium">{template.title}</div>
                    // </div>
                )}
            </div>
            <div className="flex w-full items-start justify-between">
                <div className="flex flex-col gap-[5px]">
                    <span className={'h5-new text-black-800 max-w-[110px] truncate font-semibold md:max-w-[150px]'}>{template.title || t('UNTITLED')}</span>
                    {!isPredefinedTemplate && (
                        <h1 className={'text-black-600 text-xs font-normal'}>
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
                        {template?.builderVersion !== 'v2' && (
                            <MenuItem onClick={handleClickEditCard} className="body4">
                                <ListItemIcon>
                                    <EditIcon width={20} height={20} className="text-black-600" strokeWidth={2} />
                                </ListItemIcon>
                                <span>{t('BUTTON.EDIT')}</span>
                            </MenuItem>
                        )}
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
