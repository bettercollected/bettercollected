import * as React from 'react';

import { Switch as ShadcnSwitch } from '@app/shadcn/components/ui/switch';
import { cn } from '@app/shadcn/util/lib';

// Define prop types for customization
// We maintain interface for compatibility but might not implement all style overrides perfectly without custom CSS
export interface CustomSwitchProps extends Omit<React.ComponentPropsWithoutRef<typeof ShadcnSwitch>, 'onChange'> {
    thumbColorChecked?: string;
    thumbColorUnchecked?: string;
    trackColorChecked?: string;
    trackColorUnchecked?: string;
    thumbSize?: number;
    trackBorderRadius?: number;
    onChange?: (event: any, checked: boolean) => void; // Compat
}

const CustomSwitch = React.forwardRef<React.ElementRef<typeof ShadcnSwitch>, CustomSwitchProps>(
    ({ className, onChange, onCheckedChange, checked, ...props }, ref) => {

        const handleChange = (newChecked: boolean) => {
            if (onCheckedChange) {
                onCheckedChange(newChecked);
            }
            if (onChange) {
                // Mock event
                onChange({ target: { checked: newChecked, name: props.name } }, newChecked);
            }
        };

        return (
            <ShadcnSwitch
                className={cn('data-[state=checked]:bg-primary data-[state=unchecked]:bg-input', className)}
                checked={checked}
                onCheckedChange={handleChange}
                ref={ref}
                {...props}
            />
        );
    }
);

CustomSwitch.displayName = "CustomSwitch";

export default CustomSwitch;
