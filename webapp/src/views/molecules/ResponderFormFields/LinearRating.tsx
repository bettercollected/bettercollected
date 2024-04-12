import { useEffect, useState } from 'react';

import _ from 'lodash';

import styled from 'styled-components';

import { FormField } from '@app/models/dtos/form';
import { useFormTheme } from '@app/store/jotai/fetchedForm';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';

import QuestionWrapper from './QuestionQwrapper';

const StyledDiv = styled.div<{
    $slide?: FormField;
    isBuilder: boolean;
}>(({ $slide, isBuilder = false }) => {
    const { theme } = useFormState();
    const tertiaryColor = $slide?.properties?.theme?.tertiary || theme?.tertiary;
    const secondaryColor = $slide?.properties?.theme?.secondary || theme?.secondary;

    return {
        color: secondaryColor,
        borderColor: isBuilder ? tertiaryColor : secondaryColor,
        '&:hover': {
            background: isBuilder ? '' : tertiaryColor
        }
    };
});

const LinearRatingSection = ({ field, slide, isBuilder = false }: { field: FormField; slide?: FormField; isBuilder?: boolean }) => {
    const theme = useFormTheme();
    const { formResponse, addFieldLinearRatingAnswer } = useFormResponse();
    const answer = formResponse.answers && formResponse.answers[field.id]?.number;
    const [ratingAnswer, setRatingAnswer] = useState(-1);
    const { nextField } = useResponderState();

    // useEffect(() => {
    //     formResponse.answers && setRatingAnswer((formResponse.answers[field.id]?.number ?? 0) - 1);
    // }, [formResponse.answers]);
    const secondaryColor = theme?.secondary;

    return (
        <div className="flex flex-row flex-wrap gap-1">
            {_.range(field.properties?.startFrom ?? 1, +(field.properties?.steps ?? 10) + 1, 1).map((index) => {
                return (
                    <StyledDiv
                        $slide={slide}
                        isBuilder={isBuilder}
                        style={{
                            background: answer === index ? secondaryColor : '',
                            color: answer === index ? '#ffffff' : ''
                        }}
                        key={index}
                        onClick={() => {
                            if (!isBuilder) {
                                addFieldLinearRatingAnswer(field.id, index);
                                setTimeout(() => {
                                    nextField();
                                }, 200);
                            }
                        }}
                        className="flex h-12 w-12  cursor-pointer items-center justify-center rounded-sm border-[1px]"
                    >
                        <span>{index}</span>
                    </StyledDiv>
                );
            })}
        </div>
    );
};

const LinearRatingField = ({ field, slide, isBuilder = false }: { field: FormField; slide?: FormField; isBuilder?: boolean }) => {
    return isBuilder ? (
        <LinearRatingSection field={field} slide={slide} isBuilder={isBuilder}></LinearRatingSection>
    ) : (
        <QuestionWrapper field={field}>
            <LinearRatingSection field={field} slide={slide} isBuilder={isBuilder}></LinearRatingSection>
        </QuestionWrapper>
    );
};

export default LinearRatingField;
