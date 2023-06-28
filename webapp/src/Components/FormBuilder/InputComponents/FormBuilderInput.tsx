import React from 'react';

import { TextFieldProps } from '@mui/material';

import BetterInput from '@app/components/Common/input';

export default function FormBuilderInput(props: TextFieldProps) {
    const { placeholder, ...otherProps } = props;
    return <BetterInput {...otherProps} placeholder={placeholder || 'Type your placeholder'} />;
}
