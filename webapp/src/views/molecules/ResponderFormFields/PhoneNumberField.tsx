import PhoneInput from 'react-phone-input-2';
import 'react-phone-input-2/lib/style.css';
import styled from 'styled-components';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import { getPlaceholderValueForField } from '@app/utils/formUtils';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { scrollToDivById } from '@app/utils/scrollUtils';
import QuestionWrapper from './QuestionQwrapper';

const CustomPhoneInputField = styled(PhoneInput)(() => {
    const { theme } = useFormState();
    const tertiaryColor = theme?.tertiary;
    const accentColor = theme?.accent;

    return {
        '&.react-tel-input ::placeholder': {
            color: `${tertiaryColor} !important`
        },
        '&.react-tel-input .flag-dropdown.open .selected-flag': {
            background: accentColor,
            '&:hover': {
                background: accentColor
            }
        },
        '&.react-tel-input .flag-dropdown .selected-flag': {
            background: accentColor,
            width: '40px',
            height: '40px',
            scale: 2
        },
        '&.react-tel-input .country-list .country': {
            background: accentColor,
            '&:hover': {
                background: tertiaryColor
            }
        },
        '&.react-tel-input .selected-flag .arrow': {
            border: '0px',
            borderBottom: ' 3px solid #555',
            borderRight: ' 3px solid #555',
            display: 'inline-block',
            width: '12px',
            height: '12px',
            transform: 'rotate(45deg) ',
            top: '-50%'
        },
        '&.react-tel-input .selected-flag .arrow.up': {
            border: '0px',
            borderBottom: ' 3px solid #555',
            borderRight: ' 3px solid #555',
            transform: 'rotate(225deg) ',
            top: '0%'
        }
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
                    value={(formResponse.answers && formResponse.answers[field.id]?.phone_number) || ''}
                    onChange={(e) => handleChange(e)}
                    country={'np'}
                    buttonStyle={{
                        border: '0px',
                        borderBottom: `1px solid ${theme?.tertiary}`,
                        background: theme?.accent,
                        height: '100%'
                    }}
                    dropdownStyle={{ background: theme?.accent }}
                    inputStyle={{
                        border: '0px',
                        borderBottom: `1px solid ${theme?.tertiary}`,
                        color: theme?.secondary
                    }}
                    placeholder={field?.properties?.placeholder || getPlaceholderValueForField(field.type)}
                    inputProps={{
                        className: 'text-[28px] lg:text-[32px] bg-opacity-50 mx-14 border-0 border-b-[1px] w-[93%] ',
                        id: `input-field-${field.id}`
                    }}
                />
            </form>
        </QuestionWrapper>
    );
}
