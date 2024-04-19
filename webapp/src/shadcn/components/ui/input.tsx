import * as React from 'react';

import styled from 'styled-components';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { IThemeState, useFormState } from '@app/store/jotai/form';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    textColor?: string;
}

const ShadCNInput = React.forwardRef<HTMLInputElement, InputProps>(({ className, type, textColor, ...props }, ref) => {
    const { theme } = useFormState();

    return (
        <input
            style={{
                color: theme?.secondary
            }}
            type={type}
            className={cn(`w-full border-0 border-b-[1px] px-0 py-2 text-[32px] disabled:cursor-not-allowed disabled:opacity-50`, className)}
            ref={ref}
            {...props}
        />
    );
});
ShadCNInput.displayName = 'ShadCNInput';

const FieldInput = styled(ShadCNInput)<{
    $slide?: StandardFormFieldDto;
    $formTheme?: IThemeState;
}>(({ $slide, $formTheme }) => {
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

export { FieldInput, ShadCNInput as Input };
