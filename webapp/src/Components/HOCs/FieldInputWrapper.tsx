import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { useFormState } from '@app/store/jotai/form';
import { getPlaceholderValueForField } from '@app/utils/formUtils';
import { useEffect, useState } from 'react';
import { useDebounceValue } from 'usehooks-ts';

interface IFieldInputWrapper extends React.InputHTMLAttributes<HTMLInputElement> {
    field?: StandardFormFieldDto;
    slide?: StandardFormFieldDto;
    value?: string;
    onChange: any;
    disabled?: boolean;
}

export const FieldInputWrapper = ({ field, slide, value, onChange, disabled, className, type = 'text' }: IFieldInputWrapper) => {
    const { theme } = useFormState();
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
            <FieldInput
                disabled={disabled}
                type={type}
                value={inputVal}
                style={{
                    color: slide?.properties?.theme?.tertiary || theme?.tertiary
                }}
                placeholder={getPlaceholderValueForField(field?.type || FieldTypes.SHORT_TEXT)}
                onChange={(e: any) => setInputVal(e.target.value)}
                className={className}
            />
        </>
    );
};

export default FieldInputWrapper;
