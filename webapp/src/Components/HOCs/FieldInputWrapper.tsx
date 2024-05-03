import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { useFormState } from '@app/store/jotai/form';
import { useEffect, useState } from 'react';
import { CSSProperties } from 'styled-components';
import { useDebounceValue } from 'usehooks-ts';

interface IFieldInputWrapper extends React.InputHTMLAttributes<HTMLInputElement> {
    slide?: StandardFormFieldDto;
    value?: string | number | undefined;
    onChange: any;
    disabled?: boolean;
    style?: CSSProperties;
}

export const FieldInputWrapper = ({ id, slide, value, onChange, type = 'text', style, ...props }: IFieldInputWrapper) => {
    const [inputVal, setInputVal] = useState(value);
    const [debouncedInputValue] = useDebounceValue(inputVal, 300);

    useEffect(() => {
        if (debouncedInputValue && onChange) {
            onChange(debouncedInputValue);
        }
    }, [debouncedInputValue]);

    useEffect(() => {
        value !== inputVal && setInputVal(value);
    }, [value]);

    return (
        <>
            <FieldInput id={id} type={type} value={inputVal} onChange={(e: any) => setInputVal(e.target.value)} style={style} {...props} />
        </>
    );
};

export default FieldInputWrapper;
