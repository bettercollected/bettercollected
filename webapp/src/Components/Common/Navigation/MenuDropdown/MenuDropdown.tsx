import React from 'react';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import Chevron from '@Components/Common/Icons/Chevron';
import { IconButton, IconButtonPropsSizeOverrides, Menu, PaperProps, PopoverOrigin } from '@mui/material';
import { OverridableStringUnion } from '@mui/types';

interface IMenuDropdownProps {
    id: string;
    menuTitle: string;
    menuContent: React.ReactNode | React.ReactNode[];
    children?: React.ReactNode | React.ReactNode[];
    width?: number;
    className?: string;
    onClick?: any;
    enterDelay?: number;
    leaveDelay?: number;
    enterTouchDelay?: number;
    size?: OverridableStringUnion<'small' | 'large' | 'medium', IconButtonPropsSizeOverrides>;
    fullWidth?: boolean;
    showExpandMore?: boolean;
    PaperProps?: Partial<PaperProps>;
    transformOrigin?: PopoverOrigin;
    anchorOrigin?: PopoverOrigin;
    hasMenu?: boolean;
    closeOnClick?: boolean;
}

const defaultPaperProps: PaperProps = {
    elevation: 0,
    sx: {
        overflow: 'hidden',
        borderRadius: 2,
        filter: 'drop-shadow(0px 0px 15px rgba(0, 0, 0, 0.15))',
        mt: 0.5,
        padding: 0
    }
};

const defaultTransformOrigin: PopoverOrigin = { horizontal: 'right', vertical: 'top' };
const defaultAnchorOrigin: PopoverOrigin = { horizontal: 'right', vertical: 'bottom' };

export default function MenuDropdown({
    id,
    menuTitle,
    menuContent,
    children,
    className = '',
    width = 289,
    onClick = undefined,
    enterDelay = 1000,
    leaveDelay = 100,
    enterTouchDelay = 300,
    size = 'small',
    fullWidth = false,
    showExpandMore = true,
    PaperProps = defaultPaperProps,
    transformOrigin = defaultTransformOrigin,
    anchorOrigin = defaultAnchorOrigin,
    hasMenu = true,
    closeOnClick = true
}: IMenuDropdownProps) {
    const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

    const open = Boolean(anchorEl);

    const handleClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
        if (onClick) onClick(event);
    };

    const handleClose = (e: any) => {
        e.stopPropagation();
        setAnchorEl(null);
    };

    if (width) PaperProps.sx = { ...PaperProps.sx, width: width };

    return (
        <>
            <Tooltip title={menuTitle} enterDelay={enterDelay} leaveDelay={leaveDelay} enterTouchDelay={enterTouchDelay}>
                <IconButton
                    sx={{ padding: 1 }}
                    className={`${fullWidth ? 'w-full' : 'w-fit'} flex justify-between gap-2 body3 rounded hover:rounded hover:bg-brand-100 ${className}`}
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
            {hasMenu && typeof children !== 'undefined' && (
                <Menu
                    id={id}
                    anchorEl={anchorEl}
                    open={open}
                    onClose={handleClose}
                    onClick={(event) => {
                        if (closeOnClick) handleClose(event);
                    }}
                    draggable
                    disableScrollLock={true}
                    PaperProps={PaperProps}
                    transformOrigin={transformOrigin}
                    anchorOrigin={anchorOrigin}
                >
                    {children}
                </Menu>
            )}
        </>
    );
}
