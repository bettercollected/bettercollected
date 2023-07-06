import React from 'react';

import { TextField, TextFieldProps } from '@mui/material';

export default function FormBuilderInput(props: TextFieldProps) {
    const { placeholder, inputProps, ...otherProps } = props;
    return (
        <TextField
            variant="outlined"
            inputMode="text"
            inputProps={
                inputProps || {
                    style: {
                        paddingTop: 0,
                        paddingBottom: 0,
                        height: 40,
                        fontSize: 14,
                        fontWeight: 400,
                        color: 'gray',
                        content: 'none',
                        letterSpacing: 1
                    }
                }
            }
            InputProps={{ sx: { ':before': { content: 'none' } } }}
            size="small"
            className="!mb-0 !bg-white w-full"
            {...otherProps}
            placeholder={placeholder || 'Placeholder for Input'}
        />
    );
}
