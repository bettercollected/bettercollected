import React, { forwardRef } from 'react';

import { TextField, TextFieldProps } from '@mui/material';
import cn from 'classnames';

import { ArrowDown } from '@app/components/icons/arrow-down';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';

const ConsentInput = forwardRef<HTMLDivElement, TextFieldProps>((props, ref) => {
    const { placeholder, inputProps, inputMode, className, ...otherProps } = props;

    const { t } = useBuilderTranslation();
    return (
        <TextField
            ref={ref}
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
            InputProps={{ sx: { ':before': { content: 'none' } }, endAdornment: <ArrowDown className="hover:rotate-180" /> }}
            size="small"
            className={cn('!mb-0 !bg-white w-full !text-black-300 ', className)}
            {...otherProps}
            placeholder={placeholder || t('COMPONENTS.INPUT.END_ADORNMENT_PLACEHOLDER')}
        />
    );
});

ConsentInput.displayName = 'ConsentInput';
export default ConsentInput;
