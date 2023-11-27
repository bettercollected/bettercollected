import React from 'react';

import { TextField, TextFieldProps } from '@mui/material';
import cn from 'classnames';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';

type AppTextFieldProps = TextFieldProps & {
    title?: string;
    required?: boolean;
    showIcon?: boolean;
    icon?: React.ReactNode;
    iconPosition?: 'start' | 'end';
    isError?: boolean;
    isDisabled?: boolean;
    onClick?: () => void;
    dataTestId?: string;
    childrenClassName?: string;
    disabledColor?: string;
    autoFocus?: boolean;
};

const Description: React.FC<React.PropsWithChildren> = ({ children }) => <p className="p2 pb-2 !text-new-black-800">{children}</p>;
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
        ...otherProps
    } = props;
    const { t } = useBuilderTranslation();

    const getIcon = (position: 'start' | 'end') => {
        if (position === iconPosition) {
            return icon;
        }
    };
    return (
        <div className={cn('', className)} onClick={onClick}>
            {title && (
                <div className="h4-new mb-2">
                    {title} {required && <span className="text-pink ml-2">*</span>}
                </div>
            )}
            {React.Children.map(children, (child) => {
                if (React.isValidElement(child) && child.type === Description) {
                    return child;
                }
                return null;
            })}
            <TextField
                id={id}
                autoFocus={autoFocus}
                type={type}
                variant="outlined"
                multiline={multiline}
                inputMode={inputMode || 'text'}
                disabled={isDisabled}
                inputProps={
                    inputProps || {
                        'data-testid': dataTestId,
                        style: {
                            paddingTop: 0,
                            paddingBottom: 0,
                            height: multiline ? 100 : 48,
                            fontSize: 16,
                            color: 'black',
                            fontWeight: 400,
                            content: 'none',
                            letterSpacing: 0
                        }
                    }
                }
                InputProps={{
                    sx: { ':before': { content: 'none' } },
                    startAdornment: getIcon('start'),
                    endAdornment: getIcon('end')
                }}
                size="small"
                className={cn('!mb-0 !bg-white w-full !text-black-300')}
                {...otherProps}
                placeholder={placeholder || t('COMPONENTS.INPUT.END_ADORNMENT_PLACEHOLDER')}
                sx={{
                    '& .MuiOutlinedInput-root': {
                        fieldset: {
                            borderColor: isError ? '#EA400E' : '#DBDBDB'
                        },
                        '&:hover fieldset': {
                            borderColor: isDisabled ? '' : '#343A40'
                        },
                        '&.Mui-focused fieldset': {
                            borderColor: '#B8E8FF',
                            boxShadow: '0px 0px 12px 0px rgba(7, 100, 235, 0.45)'
                        }
                    },
                    '& .MuiInputBase-input.Mui-disabled': {
                        WebkitTextFillColor: disabledColor ? disabledColor : '#AAAAAA'
                    }
                }}
                required={required}
            />
        </div>
    );
};

AppTextField.displayName = 'AppTextField';
AppTextField.Description = Description;
export default AppTextField;
