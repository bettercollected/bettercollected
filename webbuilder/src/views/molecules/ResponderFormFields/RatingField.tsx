import React, { useEffect, useState } from 'react';

import _ from 'lodash';

import { Star, StarBorder } from '@mui/icons-material';

import { FormField } from '@app/models/dtos/form';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';

import QuestionWrapper from './QuestionQwrapper';

export default function RatingField({
    field,
    slide,
    disabled = false
}: {
    field: FormField;
    slide?: FormField;
    disabled?: boolean;
}) {
    const { addFieldRatingAnswer, formResponse } = useFormResponse();
    const answer = formResponse.answers && formResponse.answers[field.id]?.number;
    const [hovered, setHovered] = useState(answer || -1);
    useEffect(() => {
        formResponse.answers &&
            setHovered((formResponse?.answers[field.id]?.number ?? 0) - 1);
    }, [formResponse.answers]);
    const { theme } = useFormState();
    const [mouseOver, setMouseOver] = useState(false);
    const RatingSection = () => {
        return (
            <div
                className="relative !mb-0 flex w-fit  flex-wrap gap-3"
                onMouseOut={() => {
                    setMouseOver(false);
                }}
                onMouseOver={() => {
                    setMouseOver(true);
                }}
            >
                {_.range(field.properties?.steps || 5).map((index) => {
                    const Component = index <= hovered ? Star : StarBorder;
                    console.log('asds ; ', mouseOver, answer);
                    return (
                        <span
                            style={{
                                color: mouseOver ? theme?.tertiary : theme?.secondary
                            }}
                            key={index}
                            onMouseOut={() => {
                                if (!disabled) setHovered((answer || 0) - 1);
                            }}
                            onClick={() => {
                                if (!disabled) {
                                    addFieldRatingAnswer(field.id, index + 1);
                                }
                            }}
                            className="cursor-pointer"
                            onMouseOver={() => {
                                if (!disabled) setHovered(index);
                            }}
                        >
                            <Component
                                fontSize="large"
                                className={`pointer-events-none  `}
                            />
                        </span>
                    );
                })}
            </div>
        );
    };
    return (
        <>
            {disabled ? (
                <RatingSection></RatingSection>
            ) : (
                <QuestionWrapper field={field}>
                    <RatingSection />
                </QuestionWrapper>
            )}
        </>
    );
}
