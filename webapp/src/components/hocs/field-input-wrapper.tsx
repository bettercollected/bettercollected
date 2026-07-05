import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput, Input } from '@app/shadcn/components/ui/input';
import { IThemeState, useFormState } from '@app/store/jotai/form';
import React, { CSSProperties, useEffect, useState } from 'react';
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

const FieldInputWrapper = ({ id, slide, value, onChange, type = 'text', style, isOptionsInput = false, ...props }: IFieldInputWrapper) => {
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
    const { theme } = useFormState();

    return (
        <>
            <Component id={id} type={type} value={inputVal} style={style} $formTheme={theme} onChange={(e: any) => setInputVal(e.target.value)} {...props} />
        </>
    );
};

const OptionInput = styled(Input)<{
    $slide?: StandardFormFieldDto;
    $formTheme?: IThemeState;
}>(({ $formTheme }) => {
    // See note in text-area-field.tsx: theme is passed as a prop, not read via a
    // hook inside the styled interpolation (avoids "Rendered fewer hooks").
    const tertiaryColor = $formTheme?.tertiary;
    const secondaryColor = $formTheme?.secondary;
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
            borderColor: secondaryColor,
            boxShadow: secondaryColor ? `0 0 0 3px ${secondaryColor}33` : undefined
        }
    };
});
OptionInput.displayName = 'OptionInput';

export default FieldInputWrapper;
