import React from 'react';

import { TextFieldProps } from '@mui/material';
import TextField from '@mui/material/TextField';

export default function BetterInput(props: TextFieldProps) {
    const { className, ...otherProps } = props;
    return <TextField {...otherProps} className={`flex-1 w-full placeholder:font-normal placeholder:text-sm placeholder:tracking-normal !mb-4 !rounded-[1px] text-gray-900 p-2.5 ` + className} />;
}
