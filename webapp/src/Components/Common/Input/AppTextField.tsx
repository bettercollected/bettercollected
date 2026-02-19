import React from 'react';

import { Input } from '@app/shadcn/components/ui/input';
import { Label } from '@app/shadcn/components/ui/label';
import { Textarea } from '@app/shadcn/components/ui/textarea';
import { cn } from '@app/shadcn/util/lib';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';

// Define a replacement for TextFieldProps since we removed MUI
// We extend basic HTML props but maintain some compatibility
type AppTextFieldProps = React.InputHTMLAttributes<HTMLInputElement | HTMLTextAreaElement> & {
    title?: string;
    required?: boolean;
    showIcon?: boolean;
    icon?: React.ReactNode;
    iconPosition?: 'start' | 'end';
    isError?: boolean;
    isDisabled?: boolean;
    isPlaceholder?: boolean;
    onClick?: () => void;
    dataTestId?: string;
    childrenClassName?: string;
    disabledColor?: string;
    autoFocus?: boolean;
    // Compatibility hooks
    multiline?: boolean;
    inputProps?: any;
    InputProps?: any; // To catch legacy usage if necessary, though we try to map it
    variant?: any;
    fullWidth?: boolean;
    rows?: number;
    helperText?: React.ReactNode;
    error?: boolean;
};

const Description: React.FC<React.PropsWithChildren> = ({ children }) => (
    <p className="p2 pb-2 !text-new-black-800 text-sm font-medium">{children}</p>
);

const AppTextField: React.FC<AppTextFieldProps> & {
    Description: React.FC<React.PropsWithChildren>;
} = (props: AppTextFieldProps) => {
    const {
        id,
        title,
        type = 'text',
        required = false,
        placeholder,
        multiline,
        inputProps,
        inputMode,
        className,
        showIcon = true,
        icon,
        children,
        iconPosition = 'start',
        isError,
        isDisabled,
        onClick,
        dataTestId = '',
        disabledColor,
        autoFocus = false,
        isPlaceholder = false,
        value,
        onChange,
        name,
        helperText,
        error,
        InputProps, // Destructure to avoid passing to DOM
        variant, // Destructure
        fullWidth, // Destructure
        ...otherProps
    } = props;
    const { t } = useBuilderTranslation();

    const isErrorState = isError || error;

    // Filter children for Description component
    const descriptionComponent = React.Children.map(children, (child) => {
        if (React.isValidElement(child) && (child.type === Description || (child.type as any).displayName === 'Description')) {
            return child;
        }
        return null;
    });

    const finalPlaceholder = placeholder || t('COMPONENTS.INPUT.END_ADORNMENT_PLACEHOLDER');

    const commonClasses = cn(
        'w-full bg-white text-black ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
        isErrorState ? 'border-red-500 focus-visible:ring-red-500' : 'border-input',
        'border rounded-md px-3 py-2 text-sm', // Base input styles from Shadcn
        // Custom styling mapping
        isPlaceholder && 'text-[#AAAAAA]',
        className
    );

    const renderInput = () => {
        if (multiline) {
            return (
                <Textarea
                    id={id}
                    name={name}
                    placeholder={finalPlaceholder}
                    value={value}
                    disabled={isDisabled}
                    required={required}
                    className={cn(commonClasses, 'min-h-[100px] resize-none')} // Match existing height 100
                    // @ts-ignore
                    inputMode={inputMode}
                    autoFocus={autoFocus}
                    onChange={onChange as React.ChangeEventHandler<HTMLTextAreaElement>}
                    {...inputProps}
                    {...otherProps}
                />
            );
        }

        return (
            <div className="relative flex items-center w-full">
                {showIcon && iconPosition === 'start' && icon && (
                    <div className="absolute left-3 flex items-center pointer-events-none text-muted-foreground">
                        {icon}
                    </div>
                )}

                {/* Support legacy InputProps.startAdornment */}
                {InputProps?.startAdornment && (
                    <div className="absolute left-3 flex items-center pointer-events-none text-muted-foreground">
                        {InputProps.startAdornment}
                    </div>
                )}

                <Input
                    id={id}
                    name={name}
                    type={type}
                    placeholder={finalPlaceholder}
                    value={value}
                    disabled={isDisabled}
                    required={required}
                    className={cn(
                        commonClasses,
                        'h-12', // Match existing height 48
                        (showIcon && iconPosition === 'start' && icon) || InputProps?.startAdornment ? 'pl-10' : '',
                        (showIcon && iconPosition === 'end' && icon) || InputProps?.endAdornment ? 'pr-10' : ''
                    )}
                    // @ts-ignore
                    inputMode={inputMode}
                    autoFocus={autoFocus}
                    onChange={onChange as React.ChangeEventHandler<HTMLInputElement>}
                    {...inputProps}
                    {...otherProps}
                />

                {showIcon && iconPosition === 'end' && icon && (
                    <div className="absolute right-3 flex items-center pointer-events-none text-muted-foreground">
                        {icon}
                    </div>
                )}

                {InputProps?.endAdornment && (
                    <div className="absolute right-3 flex items-center pointer-events-none text-muted-foreground">
                        {InputProps.endAdornment}
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className={cn('flex flex-col gap-1.5 w-full')} onClick={onClick}>
            {title && (
                <Label htmlFor={id} className={cn("text-base font-medium mb-1", required && "after:content-['*'] after:ml-0.5 after:text-pink-500")}>
                    {title}
                </Label>
            )}
            {descriptionComponent}
            {renderInput()}
            {(helperText) && (
                <p className={cn("text-xs text-muted-foreground", isErrorState && "text-red-500")}>
                    {helperText}
                </p>
            )}
            {/* Render other children that aren't Description ?? Original code seemed to only render description. */}
        </div>
    );
};

AppTextField.displayName = 'AppTextField';
AppTextField.Description = Description;
export default AppTextField;

