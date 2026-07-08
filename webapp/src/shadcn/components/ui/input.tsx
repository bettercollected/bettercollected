import * as React from 'react';

import styled from 'styled-components';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { IThemeState, useFormState } from '@app/store/jotai/form';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';

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
            className={cn(`w-full rounded-md border bg-white px-4 py-3 text-base outline-none transition duration-150 disabled:cursor-not-allowed disabled:opacity-50 lg:text-lg`, className)}
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
    const tokens = styleTokens($formTheme?.style);
    return {
        // White field on the page surface gives the input real figure/ground —
        // the bordered box, not a wash, is what reads as "type here".
        background: '#ffffff',
        borderRadius: tokens.inputRadius,
        // Resting border is deliberately SUBTLE — the theme's border colour at
        // 55% (hairline fallback) so the field sits calm at rest; hover and
        // focus below carry the strong affordance.
        borderColor: themeColor ? `${themeColor}8C` : '#CBD5E6',
        '&::placeholder': {
            // Legible neutral (ink-3), not the theme tint — placeholders are
            // text people read, not decoration.
            color: '#657085 !important'
        },
        // A field that responds to the cursor reads as inviting — hover hints
        // with the action colour; focus commits with the full ring below.
        '&:hover:not(:focus)': {
            borderColor: secondaryColor || '#2456CC'
        },
        '&:focus': {
            // Always show a focus ring for keyboard users (WCAG 2.4.7). The base
            // input sets outline:none, so without this an unthemed form would have
            // no visible focus at all. Tint from the form's theme when present,
            // else the trust-blue brand ring.
            borderColor: secondaryColor || '#2456CC',
            boxShadow: `0 0 0 3px ${secondaryColor ? `${secondaryColor}33` : 'rgba(36, 86, 204, 0.25)'}`
        }
    };
});
FieldInput.displayName = 'FieldInput';

export { AppInput, FieldInput, ShadCNInput as Input };

