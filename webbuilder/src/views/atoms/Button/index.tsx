import React, { ReactNode } from 'react';

import { CircularProgress } from '@mui/material';
import cn from 'classnames';

import { ButtonSize, ButtonVariant } from '@app/models/enums/button';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    isLoading?: boolean;
    variant?: ButtonVariant;
    size?: ButtonSize;
    icon?: ReactNode;
    postFixIcon?: ReactNode;
}

export default function Button({
    children,
    className,
    disabled,
    isLoading,
    icon,
    postFixIcon,
    variant = ButtonVariant.Primary,
    size = ButtonSize.Small,
    ...buttonProps
}: ButtonProps) {
    const getClassNamesForVariant = () => {
        switch (variant) {
            case ButtonVariant.Primary:
                return disabled
                    ? 'bg-black-300 text-black-500'
                    : 'bg-brand-500 text-white hover:bg-brand-600 active:bg-brand-800 focus:ring';
            case ButtonVariant.Secondary:
                return disabled
                    ? 'bg-black-300 text-black-500'
                    : 'bg-black-800 text-white hover:bg-black-900 focus:ring-blue-500 focus-ring active:bg-black-900';
            case ButtonVariant.Tertiary:
                return disabled
                    ? 'bg-transparent border text-black-500 border-black-300'
                    : 'text-blue-500 border border-brand-500 hover:bg-brand-100 focus:ring focus:ring-blue-500 active:bg-brand-600';
            case ButtonVariant.Danger:
                return disabled
                    ? 'bg-black-300 text-black-500'
                    : 'bg-red-400 text-white hover:bg-red-500 ';
            case ButtonVariant.Ghost:
                return disabled
                    ? 'bg-transparent text-black-500'
                    : 'text-brand-500 border border-transparent hover:bg-black-200 outline-none active:border-brand-500 active:bg-black-300';
            case ButtonVariant.DangerGhost:
                return disabled
                    ? 'bg-black-300 text-black-500'
                    : 'bg-red-100 text-red hover:bg-red-200 focus:ring-red-500 focus-ring active:bg-red-300';
        }
    };

    const getClassnamesForSize = () => {
        switch (size) {
            case ButtonSize.Medium:
                return 'h-[48px] text-sm font-medium';
            case ButtonSize.Big:
                return 'h-[64px] text-normal font-medium';
            case ButtonSize.Small:
                return 'h-[36px] text-sm';
            case ButtonSize.Tiny:
                return 'h-[28px] text-sm';
        }
    };

    return (
        <button
            disabled={isLoading || disabled}
            className={cn(
                'flex min-w-fit items-center justify-center gap-2 rounded-lg px-4',
                disabled || isLoading ? 'cursor-not-allowed' : 'cursor-pointer',
                getClassnamesForSize(),
                getClassNamesForVariant(),
                className
            )}
            {...buttonProps}
        >
            {!isLoading && icon}
            {!disabled && isLoading && <CircularProgress size={14} color="inherit" />}
            {children}
            {!isLoading && postFixIcon}
        </button>
    );
}
