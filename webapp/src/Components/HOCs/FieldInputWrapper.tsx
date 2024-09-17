import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput, Input } from '@app/shadcn/components/ui/input';
import { IThemeState, useFormState } from '@app/store/jotai/form';
import { useEffect, useState } from 'react';
import { CSSProperties } from 'styled-components';
import styled from 'styled-components';
import { useDebounceValue } from 'usehooks-ts';

interface IFieldInputWrapper extends React.InputHTMLAttributes<HTMLInputElement> {
    slide?: StandardFormFieldDto;
    value?: string | number | undefined;
    onChange: any;
    disabled?: boolean;
    style?: CSSProperties;
    isOptionsInput?: boolean;
}

export const FieldInputWrapper = ({ id, slide, value, onChange, type = 'text', style, isOptionsInput = false, ...props }: IFieldInputWrapper) => {
    const [inputVal, setInputVal] = useState(value);
    const [debouncedInputValue] = useDebounceValue(inputVal, 300);

    useEffect(() => {
        if (onChange) {
            onChange(debouncedInputValue);
        }
    }, [debouncedInputValue]);

    useEffect(() => {
        value !== inputVal && setInputVal(value);
    }, [value]);

    const Component: typeof OptionInput | typeof FieldInput = isOptionsInput ? OptionInput : FieldInput;

    return (
        <>
            <Component id={id} type={type} value={inputVal} style={style} onChange={(e: any) => setInputVal(e.target.value)} {...props} />
        </>
    );
};

const OptionInput = styled(Input)<{
    $slide?: StandardFormFieldDto;
    $formTheme?: IThemeState;
}>(({}) => {
    const { theme } = useFormState();
    const tertiaryColor = theme?.tertiary;
    const secondaryColor = theme?.secondary;
    return {
        background: 'inherit',
        borderColor: tertiaryColor,
        '&::placeholder': {
            color: `${secondaryColor} !important`
        },

        '&:focus::placeholder': {
            color: `${tertiaryColor} !important`
        },
        '&:focus': {
            borderColor: secondaryColor
        }
    };
});
OptionInput.displayName = 'OptionInput';

export default FieldInputWrapper;
