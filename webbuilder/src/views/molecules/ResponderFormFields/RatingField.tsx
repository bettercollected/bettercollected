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
    const answer = formResponse.answers && formResponse.answers[field.id].number;
    const [hovered, setHovered] = useState(answer || -1);
    useEffect(() => {
        formResponse.answers &&
            setHovered((formResponse?.answers[field.id]?.number ?? 1) - 1);
    }, [formResponse.answers]);
    console.log('sadasd : ', answer, formResponse);
    const { theme } = useFormState();
    const RatingSection = () => {
        return (
            <div className="relative !mb-0 flex w-fit  flex-wrap gap-3">
                {_.range(field.properties?.steps || 5).map((index) => {
                    const Component = index <= hovered ? Star : StarBorder;

                    return (
                        <span
                            key={index}
                        onMouseOut={() => {
                                if (!disabled) setHovered((answer || 0) - 1 || -1);
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
                                style={{
                                    color:
                                        slide?.properties?.theme?.tertiary ||
                                        theme?.tertiary
                                }}
                                fontSize="large"
                                className={`pointer-events-none ${index <= hovered ? ' text-yellow-500' : 'text-gray-400'} `}
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
