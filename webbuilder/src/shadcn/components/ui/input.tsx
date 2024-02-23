import * as React from 'react';

import { styled } from '@mui/material';

import { FormField } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import useFieldSelectorAtom from '@app/store/jotai/fieldSelector';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    textColor: string;
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

const Input = styled(ShadCNInput)(({ slide }: { slide: FormField }) => {
    // const { activeSlide: slide } = useFieldSelectorAtom();
    return {
        borderColor: slide?.properties?.theme?.tertiary,
        // '&:focus': {
        //     borderColor: slide.properties?.theme?.tertiary,
        // },
        '::placeholder': {
            color: slide?.properties?.theme?.tertiary
        }
    };
});
Input.displayName = 'Input';

export { Input };
