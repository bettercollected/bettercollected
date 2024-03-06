import * as React from 'react';

import styled from 'styled-components';

import { FormField } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { IThemeState } from '@app/store/jotai/form';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    textColor?: string;
}

const ShadCNInput = React.forwardRef<HTMLInputElement, InputProps>(
    ({ className, type, textColor, ...props }, ref) => {
        return (
            <input
                style={{
                    color: textColor
                }}
                type={type}
                className={cn(
                    `w-full border-0 border-b-[1px] px-0 py-2 text-[32px] disabled:cursor-not-allowed disabled:opacity-50`,
                    className
                )}
                ref={ref}
                {...props}
            />
        );
    }
);
ShadCNInput.displayName = 'ShadCNInput';

const FieldInput = styled(ShadCNInput)<{
    $slide?: FormField;
    $formTheme?: IThemeState;
}>(({ $slide, $formTheme }) => {
    const themeColor = $slide?.properties?.theme?.tertiary || $formTheme?.tertiary;
    return {
        borderColor: themeColor,
        '::placeholder': {
            color: `${themeColor} !important`
        }
    };
});
FieldInput.displayName = 'FieldInput';

export { FieldInput, ShadCNInput as Input };
