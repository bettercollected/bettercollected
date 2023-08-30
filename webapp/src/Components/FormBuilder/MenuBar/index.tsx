import * as React from 'react';

import Divider from '@Components/Common/DataDisplay/Divider';
import CircleOutlinedIcon from '@Components/Common/Icons/CircleOutlinedIcon';
import CoverIcon from '@Components/Common/Icons/CoverIcon';
import LoadingIcon from '@Components/Common/Icons/Loading';
import PlusIcon from '@Components/Common/Icons/Plus';
import PublishIcon from '@Components/Common/Icons/PublishIcon';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import AppBar from '@mui/material/AppBar';
import IconButton from '@mui/material/IconButton';
import InputBase from '@mui/material/InputBase';
import Toolbar from '@mui/material/Toolbar';
import { alpha, styled } from '@mui/material/styles';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
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
    isUpdating?: boolean;
}

const optionButtonClassName = 'flex flex-col text-black-700 !p-2 !md:p-3 !px-3 !md:px-5 border-1 h-full hover-none border-solid border-gray-500 md:gap-2 md:flex-row rounded-none ';

export default function FormBuilderMenuBar({ onInsert, onAddFormLogo, onAddFormCover, onPreview, onFormPublish, isUpdating }: IFormBuilderMenuBarProps) {
    const { t } = useBuilderTranslation();
    const { openModal } = useFullScreenModal();
    return (
        <AppBar
            position="static"
            className="border-b-[1px] !min-h-[40px] bg-gradient-to-b from-white to-white/80 sticky top-[68px] z-[1000] shadow-inner backdrop-blur border-black-400"
            sx={{
                borderRadius: 0,
                background: 'inherit',
                color: 'inherit',
                boxShadow: 'inherit'
            }}
        >
            <Toolbar sx={{ height: '40px !important' }} className="flex body4 w-full justify-center">
                <Divider orientation="vertical" flexItem />
                {/*<Tooltip title={t('INSERT.A_FIELD')}>*/}
                <IconButton size="small" color="inherit" className={optionButtonClassName} onClick={onInsert}>
                    <PlusIcon />
                    <span className=" text-black-700">{t('INSERT.DEFAULT')}</span>
                </IconButton>
                {/*</Tooltip>*/}
                <Divider orientation="vertical" flexItem />
                <IconButton size="small" color="inherit" className={optionButtonClassName} onClick={onAddFormLogo}>
                    <CircleOutlinedIcon />
                    <span className="hidden text-black-700 lg:flex">Logo</span>
                </IconButton>
                <Divider orientation="vertical" flexItem />
                <IconButton size="small" color="inherit" className={optionButtonClassName} onClick={onAddFormCover}>
                    <CoverIcon />
                    <span className="hidden text-black-700 lg:flex">Cover</span>
                </IconButton>
                <Divider orientation="vertical" flexItem />
                <div className="hidden md:flex md:w-20" />
                <Divider className="hidden sm:flex" orientation="vertical" flexItem />
                <Divider orientation="vertical" flexItem />

                {/*<Tooltip title={t('PREVIEW.DEFAULT')}>*/}
                <IconButton size="small" color="inherit" className={optionButtonClassName} onClick={onPreview}>
                    <VisibilityOutlinedIcon />
                    <span className=" text-black-700 ">{t('PREVIEW.DEFAULT')}</span>
                </IconButton>
                {/*</Tooltip>*/}
                <Divider orientation="vertical" flexItem />
                {/*<Tooltip title={t('PUBLISH.DEFAULT')}>*/}
                <IconButton
                    size="small"
                    color="inherit"
                    className={optionButtonClassName}
                    onClick={() => {
                        openModal('CREATE_CONSENT_FULL_MODAL_VIEW');
                    }}
                >
                    {isUpdating ? <LoadingIcon /> : <PublishIcon />}
                    <span className=" text-black-700">{t('PUBLISH.DEFAULT')}</span>
                </IconButton>
                {/*</Tooltip>*/}
                <Divider orientation="vertical" flexItem />
            </Toolbar>
        </AppBar>
    );
}
