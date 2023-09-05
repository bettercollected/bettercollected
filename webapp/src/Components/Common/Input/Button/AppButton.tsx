import React from 'react';

import { CircularProgress } from '@mui/material';
import cn from 'classnames';

interface AppButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    isLoading?: boolean;
}
export default function AppButton({ children, className, disabled, isLoading, ...buttonProps }: AppButtonProps) {
    return (
        <button disabled={isLoading || disabled} className={cn('py-2 px-4 text-white rounded w-fit !text-[14px] bg-black-900  !font-semibold ', disabled ? 'cursor-not-allowed' : 'cursor-pointer', className)} {...buttonProps}>
            {isLoading ? <CircularProgress size={20} color="inherit" /> : children}
        </button>
    );
}
