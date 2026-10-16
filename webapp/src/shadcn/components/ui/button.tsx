import * as React from 'react';
import { ReactNode } from 'react';

import { type VariantProps, cva } from 'class-variance-authority';
import { Loader2 } from 'lucide-react';

import { cn } from '@app/shadcn/util/lib';

// Buttons follow DESIGN.md: a 6px face (`rounded` = --radius) with the "key
// edge", a 3px inset bottom edge in a darker tone of the button's own colour
// (`key-edge` + `--key-edge`). Pressing moves the face down 1px and drops the
// edge. Ghost variants have no face, so they have no edge. Focus is the global
// 2px Sireto-blue outline (tailwind.css), not a per-variant ring.
const buttonVariants = cva('rounded gap-2 min-w-fit flex justify-center items-center px-2 sm:px-4 transition-colors', {
    variants: {
        variant: {
            primary: 'bg-action text-white hover:bg-action-hover active:bg-action-pressed key-edge [--key-edge:var(--color-action-pressed)] ' + 'disabled:bg-black-300 disabled:text-black-600',
            danger: 'bg-[#C43D3D] text-white hover:bg-[#A83434] active:bg-[#8F2C2C] key-edge [--key-edge:#7A2525] disabled:bg-black-300 disabled:text-black-600',
            tertiary:
                'text-brand-500 bg-white border border-brand-500 hover:bg-brand-100 active:bg-brand-200 key-edge [--key-edge:var(--color-brand-700)] ' +
                'disabled:bg-transparent disabled:border disabled:text-black-600 disabled:border-black-300',
            secondary: 'bg-black-800 text-white hover:bg-black-900 active:bg-black-900 key-edge [--key-edge:#05080F] ' + 'disabled:bg-black-300 disabled:text-black-600',
            ghost: 'text-brand-500 border border-transparent hover:bg-black-200 ' + 'active:border-brand-500 active:bg-black-300 disabled:bg-black-300 disabled:text-black-600',
            dangerGhost: 'text-[#C43D3D] border border-transparent hover:bg-[#FBEFEF] active:bg-[#F5DFDF] ' + 'disabled:bg-black-300 disabled:text-black-600',
            v2Button:
                'border border-black-400 bg-white text-black-700 hover:bg-black-200 hover:text-black-900 active:bg-black-300 key-edge [--key-edge:var(--color-black-400)] ' +
                'disabled:bg-black-300 disabled:text-black-600',
            v2GhostButton: 'text-black-600 text-xs border border-transparent hover:bg-black-200 hover:text-black-800 ' + 'active:bg-black-300 active:text-black-800 disabled:bg-black-300 disabled:text-black-600'
        },
        size: {
            medium: 'h-[48px] text-sm font-medium',
            xs: 'h-[21px] text-xs',
            sm: 'h-[40px] text-sm',
            lg: 'h-[64px] font-medium',
            icon: 'h-[28px] text-sm'
        }
    },
    defaultVariants: {
        variant: 'primary',
        size: 'sm'
    }
});

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
    icon?: ReactNode;
    isLoading?: boolean;
    postFixIcon?: ReactNode;
    /**
     * No key edge. For buttons painted in a respondent form's theme colour:
     * form themes are the creator's choice, so the app's button shape stays
     * out of them (DESIGN.md §9).
     */
    flat?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, icon, children, isLoading, postFixIcon, disabled, flat, ...props }, ref) => {
    const classes = buttonVariants({
        variant,
        size,
        className: `${disabled || isLoading ? 'cursor-not-allowed' : 'cursor-pointer'} ${className}`
    });
    return (
        <button
            disabled={disabled || isLoading}
            className={cn(flat ? classes.replace(/(^|\s)key-edge(?=\s|$)/g, ' ') : classes)}
            ref={ref}
            {...props}
        >
            {!isLoading && icon}
            {!disabled && isLoading && <Loader2 className="animate-spin" size={14} color="currentColor" />}
            {children}
            {!isLoading && postFixIcon}
        </button>
    );
});
Button.displayName = 'Button';

export { Button, buttonVariants };
