import React, { forwardRef, useImperativeHandle, useRef, useState } from 'react';

import cn from 'classnames';

import ButtonDrip from '@app/components/ui/button/button-drip';
import ButtonLoader from '@app/components/ui/button/button-loader';
import { LoaderSizeTypes, LoaderVariantTypes } from '@app/components/ui/loader';

type ShapeNames = 'rounded' | 'pill' | 'circle';
type VariantNames = 'ghost' | 'solid' | 'transparent' | 'outline';
type ColorNames = 'primary' | 'white' | 'gray' | 'success' | 'info' | 'warning' | 'danger';
type SizeNames = 'large' | 'medium' | 'small';

const shapes: Record<ShapeNames, string[]> = {
    rounded: ['rounded-[4px]'],
    pill: ['rounded-full'],
    circle: ['rounded-full']
};
const variants: Record<VariantNames, string[]> = {
    ghost: ['bg-transparent', 'p-2'],
    solid: ['text-white'],
    transparent: ['bg-transparent hover:bg-gray-50 dark:hover:bg-gray-800'],
    outline: ['text-brand-500 bg-white border-brand-300']
};
const colors: Record<ColorNames, string[]> = {
    primary: ['text-white', 'bg-brand hover:!bg-brand-600 focus:ring-brand-500', 'border-brand'],
    white: ['text-gray-900', 'bg-white focus:ring-white', 'border-white'],
    gray: ['text-gray-900', 'bg-gray-100 hover:bg-gray-200 focus:ring-gray-100', 'border-gray-100'],
    success: ['text-green-500', 'bg-green-500 hover:bg-green-200 focus:ring-green-500', 'border-green-500'],
    info: ['text-blue-500', 'bg-blue-500 hover:bg-blue-200 focus:ring-blue-500', 'border-blue-500'],
    warning: ['text-yellow-500', 'bg-yellow-500 hover:bg-yellow-200 focus:ring-yellow-500', 'border-yellow-500'],
    danger: ['text-red-500', 'bg-red-500 hover:bg-red-200 focus:ring-red-500', 'border-red-500']
};
const sizes: Record<SizeNames, string[]> = {
    large: ['py-6 px-8 h-[63px] sh1 !text-white focus:ring-1 focus:ring-offset-1'],
    medium: ['py-2 px-8 h-[46px] sh3 !text-white focus:ring-1 focus:ring-offset-1'],
    small: ['py-3 px-4 h-[36px] body4 !text-white focus:ring-1 focus:ring-offset-1']
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    isLoading?: boolean;
    disabled?: boolean;
    shape?: ShapeNames;
    variant?: VariantNames;
    color?: ColorNames;
    size?: SizeNames;
    fullWidth?: boolean;
    loaderSize?: LoaderSizeTypes;
    loaderVariant?: LoaderVariantTypes;
    onClick?: React.MouseEventHandler<HTMLButtonElement>;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
    ({ children, className, isLoading, disabled, fullWidth, shape = 'rounded', variant = 'solid', color = 'primary', size = 'small', loaderSize = 'small', loaderVariant = 'scaleUp', onClick, ...buttonProps }, ref: React.Ref<HTMLButtonElement | null>) => {
        let [dripShow, setDripShow] = useState<boolean>(false);
        let [dripX, setDripX] = useState<number>(0);
        let [dripY, setDripY] = useState<number>(0);
        const colorClassNames = colors[color];
        const sizeClassNames = sizes[size];
        const buttonRef = useRef<HTMLButtonElement>(null);
        useImperativeHandle(ref, () => buttonRef.current);

        function dripCompletedHandle() {
            setDripShow(false);
            setDripX(0);
            setDripY(0);
        }

        const clickHandler = (event: React.MouseEvent<HTMLButtonElement>) => {
            if (!isLoading && buttonRef.current) {
                const rect = buttonRef.current.getBoundingClientRect();
                setDripShow(true);
                setDripX(event.clientX - rect.left);
                setDripY(event.clientY - rect.top);
            }
            onClick && onClick(event);
        };

        let buttonColorClassNames = '';
        let buttonDripColor = '';
        switch (variant) {
            case 'ghost':
                buttonColorClassNames = `border-[1px] border-solid ${colorClassNames[0]} ${colorClassNames[2]}`;
                buttonDripColor = 'rgba(0, 0, 0, 0.1)';
                break;

            case 'transparent':
                buttonColorClassNames = `${colorClassNames[0]} ${disabled || isLoading ? '' : 'hover:bg-gray-100 dark:hover:bg-gray-800 focus:bg-gray-100 dark:focus:bg-gray-800'} `;
                buttonDripColor = 'rgba(0, 0, 0, 0.1)';
                break;

            default:
                buttonColorClassNames = `${colorClassNames[1]} ${colorClassNames[2]}`;
                buttonDripColor = 'rgba(255, 255, 255, 0.3)';
                break;
        }

        return (
            <button
                ref={buttonRef}
                onClick={clickHandler}
                className={cn(
                    'relative inline-flex shrink-0 items-center justify-center overflow-hidden text-center text-xs font-medium tracking-wider outline-none transition-all sm:text-sm',
                    !disabled ? buttonColorClassNames : 'cursor-not-allowed bg-brand-300',
                    disabled || isLoading || variant === 'transparent' || variant === 'ghost' ? '' : ' hover:shadow-md focus:shadow-large focus:outline-none',
                    isLoading && 'pointer-events-auto cursor-default focus:outline-none',
                    fullWidth && 'w-full',
                    color === 'white' || color === 'gray' ? 'text-gray-900 dark:text-white' : variants[variant],
                    shapes[shape],
                    shape === 'circle' ? `${sizeClassNames[1]}` : `${sizeClassNames[0]}`,
                    className
                )}
                disabled={disabled}
                {...buttonProps}
            >
                <span className={cn(isLoading && 'invisible opacity-0')}>{children}</span>

                {isLoading && <ButtonLoader size={loaderSize} variant={loaderVariant} />}

                {dripShow && <ButtonDrip x={dripX} y={dripY} color={['white', 'gray'].indexOf(color) !== -1 ? 'rgba(0, 0, 0, 0.1)' : buttonDripColor} fullWidth={fullWidth} onCompleted={dripCompletedHandle} />}
            </button>
        );
    }
);

Button.displayName = 'Button';
export default Button;
