import React from 'react';

import { TextFieldProps } from '@mui/material';
import TextField from '@mui/material/TextField';
import cn from 'classnames';

export function FormInputField(props: TextFieldProps) {
    const { className, ...otherProps } = props;
    return <TextField {...otherProps} className={`flex-1 w-full placeholder:font-normal placeholder:text-sm placeholder:tracking-normal rounded-[1px] text-black-900 bg-white ${className}`} />;
}
