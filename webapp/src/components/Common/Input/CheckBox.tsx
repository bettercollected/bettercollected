import React from 'react';

import { Checkbox as ShadcnCheckbox } from '@app/shadcn/components/ui/checkbox';
import { cn } from '@app/shadcn/util/lib';
// import { CheckboxProps } from '@mui/material'; // Removed

// We define our own props or extend Shadcn/Radix props
// For compatibility, we might need to handle `onChange` differenly
import * as CheckboxPrimitive from "@radix-ui/react-checkbox"

type CheckBoxProps = React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root> & {
    // Compatibility layer for MUI onChange
    // MUI: (event, checked) => void
    // HTML: (event) => void
    onChange?: (event: any, checked?: boolean) => void;
};

export default function CheckBox({ className, onChange, onCheckedChange, ...props }: CheckBoxProps) {

    const handleCheckedChange = (checked: boolean | 'indeterminate') => { // radix signature
        if (onCheckedChange) {
            onCheckedChange(checked);
        }

        if (onChange && typeof checked === 'boolean') {
            // Simulate event object for consumers expecting (event, checked)
            // This is a rough compatibility patch
            const syntheticEvent = {
                target: {
                    checked: checked,
                    name: props.name,
                    value: props.value
                },
                type: 'change'
            };
            onChange(syntheticEvent, checked);
        }
    };

    return (
        <ShadcnCheckbox
            className={cn("w-6 h-6 border-muted-foreground data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground", className)}
            onCheckedChange={handleCheckedChange}
            {...props}
        />
    );
}
