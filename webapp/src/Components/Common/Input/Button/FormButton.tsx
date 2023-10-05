import React from 'react';

import cn from 'classnames';

interface FormButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {}
export default function FormButton({ children, className, disabled, type = 'submit', ...buttonProps }: FormButtonProps) {
    return (
        <button className={cn('py-3 text-white rounded min-w-[130px] px-5 !text-[14px] bg-black-900  !font-semibold ', disabled ? 'cursor-not-allowed' : 'cursor-pointer', className)} type={type} {...buttonProps}>
            {children}
        </button>
    );
}