import { useEffect, useState } from 'react';

import _ from 'lodash';

import styled from 'styled-components';

import { FormField } from '@app/models/dtos/form';
import { useFormTheme } from '@app/store/jotai/fetchedForm';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';

import QuestionWrapper from './QuestionQwrapper';

const StyledDiv = styled.div<{
    $slide?: FormField;
    disabled: boolean;
}>(({ $slide, disabled = false }) => {
    const { theme } = useFormState();
    const tertiaryColor = $slide?.properties?.theme?.tertiary || theme?.tertiary;
    const secondaryColor = $slide?.properties?.theme?.secondary || theme?.secondary;

    return {
        color: secondaryColor,
        borderColor: disabled ? tertiaryColor : secondaryColor,
        '&:hover': {
            background: disabled ? '' : tertiaryColor
        }
    };
});

const LinearRatingSection = ({
    field,
    slide,
    disabled = false
}: {
    field: FormField;
    slide?: FormField;
    disabled?: boolean;
}) => {
    const theme = useFormTheme();
    const { formResponse, addFieldLinearRatingAnswer } = useFormResponse();
    const [ratingAnswer, setRatingAnswer] = useState(-1);
    useEffect(() => {
        formResponse.answers &&
            setRatingAnswer(formResponse.answers[field.id]?.number || -1);
    }, [formResponse.answers]);
    const secondaryColor = theme?.secondary;
    return (
        <div className="flex flex-row flex-wrap gap-1">
            {_.range(field.properties?.steps || 10).map((index) => {
                return (
                    <StyledDiv
                        $slide={slide}
                        disabled={disabled}
                        style={{
                            background: ratingAnswer === index ? secondaryColor : '',
                            color: ratingAnswer === index ? '#ffffff' : ''
                        }}
                        key={index}
                        onClick={() => {
                            if (!disabled) {
                                addFieldLinearRatingAnswer(field.id, index);
                            }
                        }}
                        className="flex h-12 w-12  cursor-pointer items-center justify-center rounded-sm border-[1px]"
                    >
                        <span>{index + 1}</span>
                    </StyledDiv>
                );
            })}
        </div>
    );
};

const LinearRatingField = ({
    field,
    slide,
    disabled = false
}: {
    field: FormField;
    slide?: FormField;
    disabled?: boolean;
}) => {
    return disabled ? (
        <LinearRatingSection
            field={field}
            slide={slide}
            disabled={disabled}
        ></LinearRatingSection>
    ) : (
        <QuestionWrapper field={field}>
            <LinearRatingSection
                field={field}
                slide={slide}
                disabled={disabled}
            ></LinearRatingSection>
        </QuestionWrapper>
    );
};

export default LinearRatingField;
