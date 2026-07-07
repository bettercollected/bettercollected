import PhoneInput from 'react-phone-input-2';
import 'react-phone-input-2/lib/style.css';
import styled from 'styled-components';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { IThemeState, useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { getPlaceholderValueForField } from '@app/utils/form-utils';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { scrollToDivById } from '@app/utils/scroll-utils';
import QuestionWrapper from './question-wrapper';

const CustomPhoneInputField = styled(PhoneInput)<{ $formTheme?: IThemeState }>(({ $formTheme }) => {
    // Theme is passed as a prop; a hook inside the styled interpolation breaks
    // the hook count under React 19 ("Rendered fewer hooks").
    const accentColor = $formTheme?.accent;

    return {
        '.selected-flag': {
            background: accentColor + " !important",
            height: '100%'
        },
    };
});

export default function PhoneNumberField({ field }: { field: StandardFormFieldDto }) {
    const { theme } = useFormState();
    const { addFieldPhoneNumberAnswer, removeAnswer, formResponse } = useFormResponse();
    const handleChange = (phone: string) => {
        if (!phone) {
            removeAnswer(field.id);
            return;
        }
        addFieldPhoneNumberAnswer(field.id, phone);
    };
    const form = useAppSelector(selectForm);
    const { currentSlide } = useResponderState();

    return (
        <QuestionWrapper field={field}>
            <form
                onSubmit={(event) => {
                    event.preventDefault();
                    if (form?.fields?.[currentSlide]?.properties?.fields?.length !== field.index + 1) scrollToDivById(form?.fields?.[currentSlide]?.properties?.fields?.[field.index + 1]?.id);
                }}
            >
                <CustomPhoneInputField
                    $formTheme={theme}
                    value={(formResponse.answers && formResponse.answers[field.id]?.phone_number) || ''}
                    onChange={(e) => handleChange(e)}
                    country={'np'}
                    buttonStyle={{
                        border: '0px',
                        borderRight: `1px solid ${theme?.tertiary}`,
                        background: '#ffffff',
                        height: '100%'
                    }}
                    dropdownStyle={{ background: '#ffffff' }}
                    inputStyle={{
                        border: `1px solid ${theme?.tertiary}`,
                        borderRadius: '12px',
                        background: '#ffffff',
                        color: theme?.primary
                    }}
                    placeholder={field?.properties?.placeholder || getPlaceholderValueForField(field.type)}
                    inputProps={{
                        className: 'text-base lg:text-lg py-3 mx-14 w-[93%] ',
                        id: `input-field-${field.id}`
                    }}
                />
            </form>
        </QuestionWrapper>
    );
}
