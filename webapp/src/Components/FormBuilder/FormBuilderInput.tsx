import React from 'react';

import { TextField, TextFieldProps } from '@mui/material';

export default function FormBuilderInput(props: TextFieldProps) {
    const { placeholder, ...otherProps } = props;
    return (
        <TextField
            variant="outlined"
            inputMode="text"
            inputProps={{
                style: {
                    paddingTop: 0,
                    paddingBottom: 0,
                    height: 40,
                    fontSize: 14,
                    fontWeight: 400,
                    content: 'none',
                    letterSpacing: 1
                }
            }}
            InputProps={{ sx: { ':before': { content: 'none' } } }}
            size="small"
            className="!mb-0 !bg-white"
            {...otherProps}
            placeholder={placeholder || 'Your placeholder'}
        />
    );
}
