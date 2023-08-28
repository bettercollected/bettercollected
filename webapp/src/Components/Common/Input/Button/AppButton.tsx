import React from 'react';

import cn from 'classnames';

interface AppButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {}
export default function AppButton({ children, className, disabled, ...buttonProps }: AppButtonProps) {
    return (
        <button className={cn('py-2 px-4 text-white rounded w-fit !text-[14px] bg-black-900  !font-semibold ', disabled ? 'cursor-not-allowed' : 'cursor-pointer', className)} {...buttonProps}>
            {children}
        </button>
    );
}
