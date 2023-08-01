import React, { forwardRef } from 'react';

import { TextField, TextFieldProps } from '@mui/material';
import cn from 'classnames';

const FormBuilderInput = forwardRef<HTMLDivElement, TextFieldProps>((props, ref) => {
    const { placeholder, inputProps, inputMode, className, ...otherProps } = props;
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
            placeholder={placeholder || 'Placeholder for Input'}
        />
    );
});

FormBuilderInput.displayName = 'FormBuilderInput';
export default FormBuilderInput;
