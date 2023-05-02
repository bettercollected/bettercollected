import React from 'react';

import Chevron from '@Components/Common/Icons/Chevron';
import { IconButton, IconButtonPropsSizeOverrides, Menu, PaperProps, PopoverOrigin, Tooltip } from '@mui/material';
import { OverridableStringUnion } from '@mui/types';

interface IMenuDropdownProps {
    id: string;
    menuTitle: string;
    menuContent: React.ReactNode | React.ReactNode[];
    children: React.ReactNode | React.ReactNode[];
    size?: OverridableStringUnion<'small' | 'large' | 'medium', IconButtonPropsSizeOverrides>;
    fullWidth?: boolean;
    showExpandMore?: boolean;
    PaperProps?: Partial<PaperProps>;
    transformOrigin?: PopoverOrigin;
    anchorOrigin?: PopoverOrigin;
}

const defaultPaperProps: PaperProps = {
    elevation: 0,
    sx: {
        width: 320,
        overflow: 'hidden',
        borderRadius: 1,
        filter: 'drop-shadow(0px 2px 8px rgba(0,0,0,0.32))',
        mt: 0.5,
        padding: 0,
        '& .MuiAvatar-root': {
            width: 32,
            height: 32,
            ml: -0.5,
            mr: 2,
            borderRadius: 1
        },
        '&:before': {
            content: '""',
            display: 'block',
            position: 'absolute',
            top: 0,
            right: 14,
            width: 10,
            height: 10,
            bgcolor: 'background.paper',
            transform: 'translateY(-50%) rotate(45deg)',
            zIndex: 0
        }
    }
};

const defaultTransformOrigin: PopoverOrigin = { horizontal: 'right', vertical: 'top' };
const defaultAnchorOrigin: PopoverOrigin = { horizontal: 'right', vertical: 'bottom' };

export default function MenuDropdown({
    id,
    menuTitle,
    menuContent,
    children,
    size = 'small',
    fullWidth = false,
    showExpandMore = true,
    PaperProps = defaultPaperProps,
    transformOrigin = defaultTransformOrigin,
    anchorOrigin = defaultAnchorOrigin
}: IMenuDropdownProps) {
    const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

    const open = Boolean(anchorEl);

    const handleClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
    };

    return (
        <>
            <Tooltip title={menuTitle} arrow enterDelay={400} enterTouchDelay={0}>
                <IconButton
                    sx={{ padding: 1 }}
                    className={`${fullWidth ? 'w-full' : 'w-fit'} flex justify-between gap-2 body3 rounded hover:rounded hover:bg-brand-200`}
                    onClick={handleClick}
                    size={size}
                    aria-controls={open ? id : undefined}
                    aria-haspopup="true"
                    aria-expanded={open ? 'true' : undefined}
                >
                    <span className="flex items-center gap-2">{menuContent}</span>
                    {showExpandMore && (
                        <div className={`${open ? '!rotate-180' : '!-rotate-0'} transition-all duration-300`}>
                            <Chevron />
                        </div>
                    )}
                </IconButton>
            </Tooltip>
            <Menu id={id} anchorEl={anchorEl} open={open} onClose={handleClose} onClick={handleClose} draggable disableScrollLock={true} PaperProps={PaperProps} transformOrigin={transformOrigin} anchorOrigin={anchorOrigin}>
                {children}
            </Menu>
        </>
    );
}
