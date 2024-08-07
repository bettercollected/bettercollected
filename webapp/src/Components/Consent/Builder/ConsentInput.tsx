import React, { forwardRef } from 'react';

import { TextField, TextFieldProps } from '@mui/material';
import cn from 'classnames';

import { ArrowDown } from '@app/Components/icons/arrow-down';
import { LinkHorizontalIcon } from '@app/Components/icons/link-horizontal-icon';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';


type ConsentInputProps = TextFieldProps & { title?: string; required?: boolean; showIcon?: boolean };

const ConsentInput = forwardRef<HTMLDivElement, ConsentInputProps>((props, ref) => {
    const { id, title, type = 'text', required = false, multiline, placeholder, inputProps, inputMode, className, showIcon = true, ...otherProps } = props;

    const { t } = useBuilderTranslation();

    const getIcon = (position: 'start' | 'end' | '') => {
        if (!showIcon) return null;

        if (type === 'text' && position === 'end') {
            return <ArrowDown />;
        } else if (type === 'url' && position === 'start') {
            return <LinkHorizontalIcon />;
        }
        return null;
    };

    return (
        <div className={cn('space-y-3', className)}>
            {title && (
                <div className="h4-new">
                    {title} {required && <span className="text-pink ml-2">*</span>}
                </div>
            )}
            <TextField
                id={id}
                ref={ref}
                type={type}
                variant="outlined"
                inputMode={inputMode || 'text'}
                inputProps={
                    inputProps || {
                        style: {
                            paddingTop: 0,
                            paddingBottom: 0,
                            height: 48,
                            fontSize: 16,
                            color: 'gray',
                            fontWeight: 400,
                            content: 'none',
                            letterSpacing: 0,
                            lineHeight: 24
                        }
                    }
                }
                InputProps={{
                    sx: { ':before': { content: 'none' } },
                    startAdornment: getIcon('start'),
                    endAdornment: getIcon('end')
                }}
                size="small"
                className={cn('!mb-0 !bg-white w-full !text-black-300 ')}
                {...otherProps}
                placeholder={placeholder || t('COMPONENTS.INPUT.END_ADORNMENT_PLACEHOLDER')}
            />
        </div>
    );
});

ConsentInput.displayName = 'ConsentInput';
export default ConsentInput;