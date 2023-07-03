import { useEffect, useState } from 'react';

import { useDispatch } from 'react-redux';

import BetterInput from '@app/components/Common/input';
import { setFormTitle } from '@app/store/form-builder/slice';

interface IFormTitleProps {
    propertyValue?: string;
    action: any;
    inputProps?: any;
}

FormProperty.defaultProps = {
    propertyValue: '',
    inputProps: {}
};

export default function FormProperty({ propertyValue, action, inputProps }: IFormTitleProps) {
    const dispatch = useDispatch();
    return (
        <>
            <BetterInput
                value={propertyValue}
                className={(inputProps.className || '') + ' !bg-white'}
                {...inputProps}
                onChange={(event) => {
                    dispatch(action(event.target.value));
                }}
            />
        </>
    );
}
