import * as React from 'react';

import styled from 'styled-components';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { IThemeState, useFormState } from '@app/store/jotai/form';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    textColor?: string;
}

const ShadCNInput = React.forwardRef<HTMLInputElement, InputProps>(({ className, type, value, ...props }, ref) => {
    const { theme } = useFormState();

    return (
        <input
            style={{
                // The answer is the responder's own words — it wears ink (theme
                // primary), never the accent/action colour. 16px floor, and never
                // larger than the 24px question (Design-Language §2).
                color: theme?.primary
            }}
            type={type}
            className={cn(`w-full rounded-xl border bg-white px-4 py-3 text-base outline-none transition-shadow disabled:cursor-not-allowed disabled:opacity-50 lg:text-lg`, className)}
            ref={ref}
            // Coerce null -> '' so a controlled input never receives a null value.
            value={value === null ? '' : value}
            {...props}
        />
    );
});
ShadCNInput.displayName = 'ShadCNInput';

const AppInput = React.forwardRef<HTMLInputElement, InputProps & { icon?: React.ReactElement }>(({ className, type, icon, ...props }, ref) => {
    return (
        <span className={cn('relative w-full')}>
            {icon && <span className="absolute left-2 top-1/2 -translate-y-1/2 text-black-400 pointer-events-none">
                {icon}
            </span>}
            <input type={type} className={cn(`border-black-200 focus:border-black-400  rounded-xl border px-3 py-2 text-[12px] focus:ring-transparent disabled:cursor-not-allowed disabled:opacity-80`, className, icon && "pl-10")} ref={ref} {...props} />
        </span>
    );
});

AppInput.displayName = 'AppInput';

const FieldInput = styled(ShadCNInput)<{
    $slide?: StandardFormFieldDto;
    $formTheme?: IThemeState;
}>(({ $formTheme }) => {
    // Theme comes in as a prop; calling useFormState() inside a styled-components
    // interpolation yields an inconsistent hook count under React 19.
    const themeColor = $formTheme?.tertiary;
    const secondaryColor = $formTheme?.secondary;
    return {
        // White field on the page surface gives the input real figure/ground —
        // the bordered box, not a wash, is what reads as "type here".
        background: '#ffffff',
        borderColor: themeColor,
        '&::placeholder': {
            // Legible neutral (ink-3), not the theme tint — placeholders are
            // text people read, not decoration.
            color: '#657085 !important'
        },
        '&:focus': {
            borderColor: secondaryColor,
            // Visible focus ring (a trust + accessibility signal), tinted from the
            // form's own theme so it stays on-brand.
            boxShadow: secondaryColor ? `0 0 0 3px ${secondaryColor}33` : undefined
        }
    };
});
FieldInput.displayName = 'FieldInput';

export { AppInput, FieldInput, ShadCNInput as Input };

