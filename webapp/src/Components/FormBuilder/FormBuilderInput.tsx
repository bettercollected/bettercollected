import React from 'react';

import { TextField, TextFieldProps } from '@mui/material';
import cn from 'classnames';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';

export default function FormBuilderInput(props: TextFieldProps) {
    const { placeholder, inputProps, inputMode, className, ...otherProps } = props;

    const { t } = useBuilderTranslation();
    return (
        <TextField
            variant="outlined"
            inputMode={inputMode || 'text'}
            inputProps={
                inputProps || {
                    style: {
                        paddingTop: 0,
                        paddingBottom: 0,
                        height: 40,
                        fontSize: 14,
                        color: 'gray',
                        fontWeight: 400,
                        content: 'none',
                        letterSpacing: 1
                    }
                }
            }
            InputProps={{ sx: { ':before': { content: 'none' } } }}
            size="small"
            className={cn('!mb-0 !bg-white w-full !text-black-300 ', className)}
            {...otherProps}
            placeholder={placeholder || t('COMPONENTS.INPUT.END_ADORNMENT_PLACEHOLDER')}
        />
    );
}
