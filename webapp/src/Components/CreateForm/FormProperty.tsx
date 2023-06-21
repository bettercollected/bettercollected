import { useState } from 'react';

import { useDispatch } from 'react-redux';

import BetterInput from '@app/components/Common/input';
import { setFormTitle } from '@app/store/create-form/slice';

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
    const [value, setValue] = useState(propertyValue || '');

    return (
        <>
            <BetterInput
                className={(inputProps.className || '') + ' !bg-white'}
                {...inputProps}
                onChange={(event) => {
                    setValue(event.target.value);
                }}
                onBlur={(e) => {
                    dispatch(action(value));
                }}
            />
        </>
    );
}
