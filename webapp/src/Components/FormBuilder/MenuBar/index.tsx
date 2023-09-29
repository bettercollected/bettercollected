import * as React from 'react';

import CustomPopover from '@Components/Common/CustomPopover';
import Divider from '@Components/Common/DataDisplay/Divider';
import CircleOutlinedIcon from '@Components/Common/Icons/CircleOutlinedIcon';
import CoverIcon from '@Components/Common/Icons/CoverIcon';
import InfoIcon from '@Components/Common/Icons/FormBuilder/infoIcon';
import LoadingIcon from '@Components/Common/Icons/Loading';
import PlusIcon from '@Components/Common/Icons/Plus';
import PublishIcon from '@Components/Common/Icons/PublishIcon';
import { DragHandle } from '@mui/icons-material';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import AppBar from '@mui/material/AppBar';
import IconButton from '@mui/material/IconButton';
import InputBase from '@mui/material/InputBase';
import Toolbar from '@mui/material/Toolbar';
import { alpha, styled } from '@mui/material/styles';
import cn from 'classnames';

import Hamburger from '@app/components/ui/hamburger';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';

const Search = styled('div')(({ theme }) => ({
    position: 'relative',
    borderRadius: theme.shape.borderRadius,
    backgroundColor: alpha(theme.palette.common.white, 0.15),
    '&:hover': {
        backgroundColor: alpha(theme.palette.common.white, 0.25)
    },
    marginRight: theme.spacing(2),
    marginLeft: 0,
    width: '100%',
    [theme.breakpoints.up('sm')]: {
        marginLeft: theme.spacing(3),
        width: 'auto'
    }
}));

const SearchIconWrapper = styled('div')(({ theme }) => ({
    padding: theme.spacing(0, 2),
    height: '100%',
    position: 'absolute',
    pointerEvents: 'none',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
}));

const StyledInputBase = styled(InputBase)(({ theme }) => ({
    color: 'inherit',
    '& .MuiInputBase-input': {
        padding: theme.spacing(1, 1, 1, 0),
        // vertical padding + font size from searchIcon
        paddingLeft: `calc(1em + ${theme.spacing(4)})`,
        transition: theme.transitions.create('width'),
        width: '100%',
        [theme.breakpoints.up('md')]: {
            width: '20ch'
        }
    }
}));

interface IFormBuilderMenuBarProps {
    onInsert: React.MouseEventHandler<HTMLButtonElement>;
    onAddNewPage: React.MouseEventHandler<HTMLButtonElement>;
    onAddFormLogo: React.MouseEventHandler<HTMLButtonElement>;
    onAddFormCover: React.MouseEventHandler<HTMLButtonElement>;
    onPreview: React.MouseEventHandler<HTMLButtonElement>;
    onFormPublish: React.MouseEventHandler<HTMLButtonElement>;
    onClickSettings: React.MouseEventHandler<HTMLButtonElement>;
    onClickTips: React.MouseEventHandler<HTMLButtonElement>;
    isUpdating?: boolean;
}

export default function FormBuilderMenuBar({ onInsert, onAddFormLogo, onAddFormCover, onClickSettings, onClickTips, onPreview, onFormPublish, isUpdating }: IFormBuilderMenuBarProps) {
    const { t } = useBuilderTranslation();

    const breakpoint = useBreakpoint();

    const collapseMenu = ['2xs', 'xs', 'sm', 'md'].indexOf(breakpoint) !== -1;

    const optionButtonClassName =
        'flex text-black-700  text-sm lg:text-normal justify-start px-5 !py-3 !lg:p-2 !lg:p-3 lg:!px-3 !lg:px-5 border-1   lg:w-fit w-full hover-none border-solid border-gray-500 md:gap-2 rounded-none ' + (collapseMenu ? 'h-fit' : 'h-[64px]');

    const Actions = () => (
        <Toolbar className=" !px-0 lg:px-6 divide-y divide-black-200 lg:divide-y-0  flex flex-col lg:flex-row body4 w-full justify-center">
            {/*<Divider orientation="vertical" className="hidden lg:flex" flexItem />*/}
            {/*<IconButton color="inherit" className={optionButtonClassName} onClick={onInsert}>*/}
            {/*    <PlusIcon />*/}
            {/*    <span className=" text-black-700">{t('INSERT.DEFAULT')}</span>*/}
            {/*</IconButton>*/}
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

            <IconButton size="small" color="inherit" className={optionButtonClassName} onClick={onClickTips}>
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
            <IconButton color="inherit" className={optionButtonClassName} onClick={onFormPublish}>
                {isUpdating ? <LoadingIcon /> : <PublishIcon />}
                <span className=" text-black-700">{t('PUBLISH.DEFAULT')}</span>
            </IconButton>
            {/*</Tooltip>*/}
            <Divider orientation="vertical" className="hidden lg:flex" flexItem />
        </Toolbar>
    );
    return (
        <AppBar
            position="static"
            className="border-b-[1px] !min-h-[40px]  bg-gradient-to-b from-white to-white/80 sticky items-center justify-center flex top-[68px] z-[1000] shadow-inner backdrop-blur border-black-400"
            sx={{
                borderRadius: 0,
                background: 'inherit',
                color: 'inherit',
                boxShadow: 'inherit'
            }}
        >
            {collapseMenu ? (
                <CustomPopover
                    content={
                        <div className="min-w-[200px]">
                            <Actions />
                        </div>
                    }
                >
                    <div className="h-16 flex gap-2 items-center rounded px-5 hover:cursor-pointer hover:bg-black-200">
                        <Hamburger /> Actions
                    </div>
                </CustomPopover>
            ) : (
                <Actions />
            )}
        </AppBar>
    );
}
