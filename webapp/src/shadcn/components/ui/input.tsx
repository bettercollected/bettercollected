import * as React from 'react';

import styled from 'styled-components';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { IThemeState, useFormState } from '@app/store/jotai/form';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    textColor?: string;
}

const ShadCNInput = React.forwardRef<HTMLInputElement, InputProps>(({ className, type, ...props }, ref) => {
    const { theme } = useFormState();

    return (
        <input
            style={{
                color: theme?.secondary
            }}
            type={type}
            className={cn(`w-full border-0 border-b-[1px] px-0 py-2 text-[28px] disabled:cursor-not-allowed disabled:opacity-50 lg:text-[32px]`, className)}
            ref={ref}
            {...props}
        />
    );
});
ShadCNInput.displayName = 'ShadCNInput';

const AppInput = React.forwardRef<HTMLInputElement, InputProps>(({ className, type, ...props }, ref) => {
    return <input type={type} className={cn(`border-black-200 focus:border-black-400 w-full rounded-xl border px-3 py-2 text-[12px] focus:ring-transparent disabled:cursor-not-allowed disabled:opacity-50`, className)} ref={ref} {...props} />;
});

AppInput.displayName = 'AppInput';

const FieldInput = styled(ShadCNInput)<{
    $slide?: StandardFormFieldDto;
    $formTheme?: IThemeState;
}>(({}) => {
    const { theme } = useFormState();
    const themeColor = theme?.tertiary;
    const secondaryColor = theme?.secondary;
    return {
        background: 'inherit',
        borderColor: themeColor,
        '&::placeholder': {
            color: `${themeColor} !important`
        },
        '&:focus': {
            borderColor: secondaryColor
        }
    };
});
FieldInput.displayName = 'FieldInput';

export { FieldInput, ShadCNInput as Input, AppInput };
