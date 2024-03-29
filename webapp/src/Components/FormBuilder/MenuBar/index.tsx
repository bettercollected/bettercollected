import * as React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import CustomPopover from '@Components/Common/CustomPopover';
import Divider from '@Components/Common/DataDisplay/Divider';
import PlusIcon from '@Components/Common/Icons/Common/Plus';
import PublishIcon from '@Components/Common/Icons/FormBuilder/PublishIcon';
import InfoIcon from '@Components/Common/Icons/FormBuilder/infoIcon';
import CircleOutlinedIcon from '@Components/Common/Icons/Header/CircleOutlinedIcon';
import CoverIcon from '@Components/Common/Icons/Header/CoverIcon';
import HamburgerIcon from '@Components/Common/Icons/Header/HamburgerIcon';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import MakeTemplateButton from '@Components/Template/MakeTemplateButton';
import { ChevronLeft } from '@mui/icons-material';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import AppBar from '@mui/material/AppBar';
import IconButton from '@mui/material/IconButton';
import Toolbar from '@mui/material/Toolbar';

import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';


interface IFormBuilderMenuBarProps {
    onAddNewPage: React.MouseEventHandler<HTMLButtonElement>;
    onAddFormLogo: React.MouseEventHandler<HTMLButtonElement>;
    onAddFormCover: React.MouseEventHandler<HTMLButtonElement>;
    onPreview: React.MouseEventHandler<HTMLButtonElement>;
    onFormPublish: React.MouseEventHandler<HTMLButtonElement>;
    onClickTips: React.MouseEventHandler<HTMLButtonElement>;
    onSaveTemplate?: React.MouseEventHandler<HTMLButtonElement>;
    onClickInsert: React.MouseEventHandler<HTMLButtonElement>;
    isUpdating?: boolean;
    isTemplate: boolean;
}

function FormBuilderMenuBar({ onAddFormLogo, onAddFormCover, onClickTips, onPreview, onFormPublish, isTemplate, onSaveTemplate, onClickInsert }: IFormBuilderMenuBarProps) {
    const { t } = useBuilderTranslation();

    const { t: translation } = useTranslation();

    const breakpoint = useBreakpoint();

    const router = useRouter();

    const collapseMenu = ['2xs', 'xs', 'sm', 'md'].indexOf(breakpoint) !== -1;

    const optionButtonClassName =
        'flex text-black-700  text-sm lg:text-normal justify-start px-5 !py-3 !lg:p-2 !lg:p-3 lg:!px-3 !lg:px-5 border-1   lg:w-fit w-full hover-none border-solid border-gray-500 md:gap-2 rounded-none ' + (collapseMenu ? 'h-fit' : 'h-[48px]');

    const Actions = () => (
        <Toolbar className=" !px-0 lg:px-6 divide-y divide-black-200 lg:divide-y-0  flex flex-col lg:flex-row body4 w-full relative justify-center" variant={'dense'}>
            <Divider orientation="vertical" className="hidden lg:flex" flexItem />
            <IconButton color="inherit" className={optionButtonClassName} onClick={onClickInsert}>
                <PlusIcon />
                <span className="text-black-700 ">Insert</span>
            </IconButton>
            <Divider orientation="vertical" className="hidden lg:flex" flexItem />
            <Divider orientation="vertical" className="hidden lg:flex" flexItem />
            <IconButton color="inherit" className={optionButtonClassName} onClick={onAddFormLogo}>
                <CircleOutlinedIcon />
                <span className="text-black-700 ">Logo</span>
            </IconButton>
            <Divider orientation="vertical" className="hidden lg:flex" flexItem />
            <IconButton color="inherit" className={optionButtonClassName} onClick={onAddFormCover}>
                <CoverIcon />
                <span className="text-black-700">Cover</span>
            </IconButton>
            <Divider orientation="vertical" className="hidden lg:flex" flexItem />
            <div className="hidden lg:flex lg:w-20" />
            <Divider orientation="vertical" className="hidden lg:flex" flexItem />
            <IconButton size="small" color="inherit" className={optionButtonClassName + ' hidden lg:flex'} onClick={onClickTips}>
                <InfoIcon />
                <span className=" text-black-700 ">Tips</span>
            </IconButton>
            {/* <IconButton size="small" color="inherit" className={optionButtonClassName} onClick={onClickSettings}>
                    <SettingsIcon />
                    <span className=" text-black-700 ">Settings</span>
                </IconButton> */}
            <Divider orientation="vertical" className="hidden lg:flex" flexItem />
            {!collapseMenu && <Divider orientation="vertical" className="hidden lg:flex" flexItem />}

            <IconButton color="inherit" className={optionButtonClassName} onClick={onPreview}>
                <VisibilityOutlinedIcon />
                <span className=" text-black-700 ">{t('PREVIEW.DEFAULT')}</span>
            </IconButton>
            {/*</Tooltip>*/}
            <Divider orientation="vertical" className="hidden lg:flex" flexItem />
            {/*<Tooltip title={t('PUBLISH.DEFAULT')}>*/}
            {/*</Tooltip>*/}
            <Divider orientation="vertical" className="hidden lg:flex" flexItem />
            <div className={'absolute right-10 hidden lg:flex gap-4'}>
                {isTemplate ? (
                    <AppButton onClick={onSaveTemplate}>{translation('TEMPLATE.BUTTONS.SAVE_TEMPLATE')}</AppButton>
                ) : (
                    <>
                        <MakeTemplateButton />
                        <AppButton icon={<PublishIcon />} onClick={onFormPublish}>
                            {t('PUBLISH.DEFAULT')}
                        </AppButton>
                    </>
                )}
            </div>
        </Toolbar>
    );
    return (
        <AppBar
            position="static"
            className="border-b-[1px] !min-h-[48px]  bg-gradient-to-b from-white to-white/80 sticky items-center justify-center flex top-[68px] z-[1000] shadow-inner backdrop-blur border-black-400"
            sx={{
                borderRadius: 0,
                background: 'inherit',
                color: 'inherit',
                boxShadow: 'inherit'
            }}
        >
            {collapseMenu ? (
                <div className="relative flex items-center gap-6 justify-center w-full">
                    <button
                        className="absolute flex items-center text-black-700 gap-1 text-sm left-5 lg:hidden"
                        onClick={() => {
                            router.back();
                        }}
                    >
                        <ChevronLeft className="h-6 w-6 " />
                        {translation('BUTTON.BACK')}
                    </button>
                    <CustomPopover
                        content={
                            <div className="min-w-[200px]">
                                <Actions />
                            </div>
                        }
                    >
                        <div className="flex text-black-800 gap-2 items-center rounded hover:cursor-pointer">
                            <HamburgerIcon width={24} height={24} />
                        </div>
                    </CustomPopover>
                    {isTemplate ? (
                        <AppButton variant={ButtonVariant.Ghost} className={'absolute right-5 lg:hidden'} onClick={onSaveTemplate}>
                            {translation('TEMPLATE.BUTTONS.SAVE_TEMPLATE')}
                        </AppButton>
                    ) : (
                        <>
                            <MakeTemplateButton buttonType={ButtonVariant.Ghost} />
                            <AppButton variant={ButtonVariant.Ghost} className={'absolute right-5 lg:hidden'} onClick={onFormPublish}>
                                {t('PUBLISH.DEFAULT')}
                            </AppButton>
                        </>
                    )}
                </div>
            ) : (
                <Actions />
            )}
        </AppBar>
    );
}

export default React.memo(FormBuilderMenuBar);