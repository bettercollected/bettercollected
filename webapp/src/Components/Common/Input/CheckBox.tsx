import React from 'react';

import { Checkbox, CheckboxProps } from '@mui/material';

export default function CheckBox({ ...props }: CheckboxProps) {
    return (
        <Checkbox
            className="!p-0 !border !border-new-black-300"
            sx={{
                color: '#DBDBDB',
                width: '24px',
                height: '24px',
                border: '1px',
                padding: '0px',
                '&.Mui-disabled': {
                    border: '1px',
                    padding: '0px'
                },
                '&.Mui-hover': {
                    color: 'white'
                }
            }}
            {...props}
        />
    );
}
