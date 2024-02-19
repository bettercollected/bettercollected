import * as React from "react"
import {Slot} from "@radix-ui/react-slot"
import {cva, type VariantProps} from "class-variance-authority"

import {cn} from "@app/shadcn/util/lib"
import {ReactNode} from "react";
import {CircularProgress} from "@mui/material";

const buttonVariants = cva(
    "rounded-lg gap-2 min-w-fit flex justify-center items-center px-4",
    {
        variants: {
            variant: {
                primary: "bg-brand-500 text-white hover:bg-brand-600 active:bg-brand-800 focus:ring " +
                    "disabled:bg-black-300 disabled:text-black-500",
                danger:
                    "bg-red-400 text-white hover:bg-red-500 disabled:bg-black-300 disabled:text-black-500",
                tertiary:
                    "text-blue-500 border border-brand-500 hover:bg-brand-100 focus:ring focus:ring-blue-500 " +
                    "active:bg-brand-600 disabled:bg-transparent disabled:border disabled:text-black-500 " +
                    "disabled:border-black-300",
                secondary:
                    "bg-black-800 text-white hover:bg-black-900 focus:ring-blue-500 focus-ring active:bg-black-900" +
                    "disabled:bg-black-300 disabled:text-black-500",
                ghost: "text-brand-500 border border-transparent hover:bg-black-200 outline-none " +
                    "active:border-brand-500 active:bg-black-300 disabled:bg-black-300 disabled:text-black-500",
                dangerGhost: "bg-red-100 text-red hover:bg-red-200 focus:ring-red-500 focus-ring active:bg-red-300" +
                    "disabled:bg-black-300 disabled:text-black-500",
            },
            size: {
                medium: "h-[48px] text-sm font-medium",
                sm: "h-[36px] text-sm",
                lg: "h-[64px] text-normal font-medium",
                icon: "h-[28px] text-sm",
            },
        },
        defaultVariants: {
            variant: "primary",
            size: "sm",
        },
    }
)

export interface ButtonProps
    extends React.ButtonHTMLAttributes<HTMLButtonElement>,
        VariantProps<typeof buttonVariants> {
    icon?: ReactNode;
    isLoading?: boolean;
    postFixIcon?: ReactNode;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
    ({className, variant, size, icon, children, isLoading, postFixIcon, disabled, ...props}, ref) => {
        return (
            <button
                disabled={disabled || isLoading}
                className={cn(buttonVariants({
                    variant,
                    size,
                    className:`${className}${disabled || isLoading ? 'cursor-not-allowed' : 'cursor-pointer'  }` ,
                }))}
                ref={ref}
                {...props}
            >
                {!isLoading && icon}
                {!disabled && isLoading && <CircularProgress size={14} color="inherit"/>}
                {children}
                {!isLoading && postFixIcon}
            </button>
        )
    }
)
Button.displayName = "Button"

export {Button, buttonVariants}
