import React, { forwardRef } from 'react';

import { TextField, TextFieldProps } from '@mui/material';
import cn from 'classnames';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';

type AppTextFieldProps = TextFieldProps & { title?: string; required?: boolean; showIcon?: boolean; icon?: React.ReactNode; iconPosition?: 'start' | 'end' };

const Description: React.FC<React.PropsWithChildren> = ({ children }) => <p className="p2 py-2 !text-new-black-800">{children}</p>;
const AppTextField: React.FC<AppTextFieldProps> & { Description: React.FC<React.PropsWithChildren> } = (props: AppTextFieldProps) => {
    const { id, title, type = 'text', required = false, placeholder, multiline, inputProps, inputMode, className, showIcon = true, icon, children, iconPosition = 'start', ...otherProps } = props;
    const { t } = useBuilderTranslation();

    const getIcon = (position: 'start' | 'end') => {
        if (position === iconPosition) {
            return icon;
        }
    };
    return (
        <div className={cn('', className)}>
            {title && (
                <div className="h5-new mb-3">
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
                type={type}
                variant="outlined"
                multiline={multiline}
                inputMode={inputMode || 'text'}
                inputProps={
                    inputProps || {
                        style: {
                            paddingTop: 0,
                            paddingBottom: 0,
                            height: multiline ? 152 : 48,
                            fontSize: 16,
                            color: 'gray',
                            fontWeight: 400,
                            content: 'none',
                            letterSpacing: 0,
                            lineHeight: 24
                        }
                    }
                }
                InputProps={{ sx: { ':before': { content: 'none' } }, startAdornment: getIcon('start'), endAdornment: getIcon('end') }}
                size="small"
                className={cn('!mb-0 !bg-white w-full !text-black-300 ')}
                {...otherProps}
                placeholder={placeholder || t('COMPONENTS.INPUT.END_ADORNMENT_PLACEHOLDER')}
            />
        </div>
    );
};

AppTextField.displayName = 'AppTextField';
AppTextField.Description = Description;
export default AppTextField;
