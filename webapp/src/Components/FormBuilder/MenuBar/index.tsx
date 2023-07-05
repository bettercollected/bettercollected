import * as React from 'react';

import Divider from '@Components/Common/DataDisplay/Divider';
import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import ImageOutlinedIcon from '@mui/icons-material/ImageOutlined';
import PanoramaHorizontalIcon from '@mui/icons-material/PanoramaHorizontal';
import PostAddIcon from '@mui/icons-material/PostAdd';
import PublishOutlinedIcon from '@mui/icons-material/PublishOutlined';
import TextFieldsOutlinedIcon from '@mui/icons-material/TextFieldsOutlined';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import AppBar from '@mui/material/AppBar';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import InputBase from '@mui/material/InputBase';
import Toolbar from '@mui/material/Toolbar';
import { alpha, styled } from '@mui/material/styles';

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
}

export default function FormBuilderMenuBar({ onInsert, onAddNewPage, onAddFormLogo, onAddFormCover, onPreview, onFormPublish }: IFormBuilderMenuBarProps) {
    return (
        <AppBar position="static" className="border-b-[1px] border-black-400" sx={{ borderRadius: 0, background: 'inherit', color: 'inherit', boxShadow: 'inherit' }}>
            <Toolbar>
                <Box
                    sx={{
                        flexGrow: 1,
                        display: 'flex',
                        alignItems: 'center',
                        width: 'fit-content',
                        bgcolor: 'background.paper',
                        color: 'text.secondary',
                        '& svg': {
                            m: 1
                        },
                        '& hr': {
                            mx: 1
                        }
                    }}
                >
                    <Tooltip title="Insert a field">
                        <IconButton size="small" color="inherit" className="flex flex-col rounded-none aspect-square" onClick={onInsert}>
                            <TextFieldsOutlinedIcon />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Add a new page">
                        <IconButton size="small" color="inherit" className="flex flex-col rounded-none" onClick={onAddNewPage}>
                            <PostAddIcon />
                        </IconButton>
                    </Tooltip>
                    <Divider orientation="vertical" flexItem />
                    <Tooltip title="Add a form logo">
                        <IconButton size="small" color="inherit" className="flex flex-col rounded-none" onClick={onAddFormLogo}>
                            <ImageOutlinedIcon />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Add a form cover">
                        <IconButton size="small" color="inherit" className="flex flex-col rounded-none" onClick={onAddFormCover}>
                            <PanoramaHorizontalIcon />
                        </IconButton>
                    </Tooltip>
                    <Divider orientation="vertical" flexItem />
                </Box>
                <Box
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        width: 'fit-content',
                        bgcolor: 'background.paper',
                        color: 'text.secondary',
                        '& svg': {
                            m: 1
                        },
                        '& hr': {
                            mx: 1
                        }
                    }}
                >
                    <Tooltip title="Preview">
                        <IconButton size="small" color="inherit" className="flex flex-col rounded-none" onClick={onPreview}>
                            <VisibilityOutlinedIcon />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Publish">
                        <IconButton size="small" color="inherit" className="flex flex-col rounded-none" onClick={onFormPublish}>
                            <PublishOutlinedIcon />
                        </IconButton>
                    </Tooltip>
                </Box>
            </Toolbar>
        </AppBar>
    );
}
