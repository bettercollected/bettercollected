import React from 'react';

import { ButtonClasses, ButtonPropsVariantOverrides, ClassNameMap, Button as MuiButton, SxProps, Theme } from '@mui/material';
import { TouchRippleProps } from '@mui/material/ButtonBase/TouchRipple';
import { OverridableStringUnion } from '@mui/types';

interface IButtonProps {
    onClick: React.MouseEventHandler<HTMLButtonElement>;
    children: React.ReactNode;
    size?: 'small' | 'medium' | 'large';
    className?: string;
    color?: string;
    centerRipple?: boolean;
    classes?: Partial<ButtonClasses> & Partial<ClassNameMap<never>>;
    disabled?: boolean;
    disableRipple?: boolean;
    disableTouchRipple?: boolean;
    focusRipple?: boolean;
    focusVisibleClassName?: string;
    sx?: SxProps<Theme>;
    TouchRippleProps?: Partial<TouchRippleProps>;
    variant?: OverridableStringUnion<'text' | 'outlined' | 'contained', ButtonPropsVariantOverrides>;
}

export default function Button({
    onClick,
    children,
    size = 'small',
    className = '',
    centerRipple = false,
    classes = {},
    disabled = false,
    disableRipple = false,
    disableTouchRipple = false,
    focusVisibleClassName = '',
    sx = {},
    color,
    TouchRippleProps = {},
    variant = 'contained'
}: IButtonProps) {
    const smallSx: SxProps<Theme> = {};
    const mediumSx: SxProps<Theme> = {};
    const largeSx: SxProps<Theme> = {};

    const textVariant: SxProps<Theme> = size === 'large' ? { ...largeSx, ...sx } : size === 'medium' ? { ...mediumSx, ...sx } : { ...smallSx, ...sx };
    const outlinedVariant: SxProps<Theme> = size === 'large' ? { ...largeSx, ...sx } : size === 'medium' ? { ...mediumSx, ...sx } : { ...smallSx, ...sx };
    const containedVariant: SxProps<Theme> = size === 'large' ? { ...largeSx, ...sx } : size === 'medium' ? { ...mediumSx, ...sx } : { ...smallSx, ...sx };

    const newSx = variant === 'text' ? { ...textVariant } : variant === 'outlined' ? { ...outlinedVariant } : { ...containedVariant };

    return (
        <MuiButton
            className={className}
            onClick={onClick}
            color={color}
            centerRipple={centerRipple}
            classes={classes}
            disabled={disabled}
            disableRipple={disableRipple}
            disableTouchRipple={disableTouchRipple}
            focusVisibleClassName={focusVisibleClassName}
            variant={variant}
            TouchRippleProps={TouchRippleProps}
            sx={newSx}
        >
            {children}
        </MuiButton>
    );
}
