import React, { ReactNode } from 'react';

import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { CircularProgress } from '@mui/material';
import cn from 'classnames';

export interface AppButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    isLoading?: boolean;
    variant?: ButtonVariant;
    size?: ButtonSize;
    icon?: ReactNode;
    postFixIcon?: ReactNode;
}

export default function AppButton({ children, className, disabled, isLoading, icon, postFixIcon, variant = ButtonVariant.Primary, size = ButtonSize.Small, ...buttonProps }: AppButtonProps) {
    const getClassNamesForVariant = () => {
        switch (variant) {
            case ButtonVariant.Primary:
                return disabled ? 'bg-black-300 text-black-500' : 'bg-brand-500 text-white hover:bg-brand-600 active:bg-brand-800 focus:ring';
            case ButtonVariant.Secondary:
                return disabled ? 'bg-black-300 text-black-500' : 'bg-black-800 text-white hover:bg-black-900 focus:ring focus:ring-brand-500 active:bg-black-800';
            case ButtonVariant.Tertiary:
                return disabled ? 'bg-transparent border text-black-500 border-black-300' : 'text-blue-500 border border-brand-500 hover:bg-brand-500 hover:text-white focus:ring focus:ring-blue-500 active:bg-brand-600';
            case ButtonVariant.Danger:
                return disabled ? 'bg-black-300 text-black-500' : 'bg-red-400 text-white hover:bg-red-500 active:bg-red-400 focus:ring focus:ring-blue-700';
            case ButtonVariant.Ghost:
                return disabled ? 'bg-transparent text-black-500' : 'text-brand-500 border border-transparent hover:bg-black-200 outline-none active:border-brand-500 active:bg-black-300';
            case ButtonVariant.DangerGhost:
                return disabled ? 'bg-black-300 text-black-500' : 'bg-red-100 text-red hover:bg-red-200 focus:ring-red-500 focus-ring active:bg-red-300';
        }
    };

    const getClassnamesForSize = () => {
        switch (size) {
            case ButtonSize.Medium:
                return 'h-[48px] text-sm';
            case ButtonSize.Big:
                return 'h-[64px] text-normal';
            case ButtonSize.Small:
                return 'h-[36px] text-sm';
            case ButtonSize.Tiny:
                return 'h-[28px] text-sm';
        }
    };

    return (
        <button
            disabled={isLoading || disabled}
            className={cn('rounded gap-2 min-w-fit flex justify-center items-center px-4', disabled || isLoading ? 'cursor-not-allowed' : 'cursor-pointer', getClassnamesForSize(), getClassNamesForVariant(), className)}
            {...buttonProps}
        >
            {!isLoading && icon}
            {!disabled && isLoading && <CircularProgress size={14} color="inherit" />}
            {children}
            {!isLoading && postFixIcon}
        </button>
    );
}
