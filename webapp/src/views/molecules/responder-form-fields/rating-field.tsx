import { useState } from 'react';

import _ from 'lodash';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { StarIcon } from '@Components/icons/start';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { scrollToDivById } from '@app/utils/scroll-utils';
import QuestionWrapper from './question-wrapper';

export default function RatingField({ field, slide, isBuilder = false }: { field: StandardFormFieldDto; slide?: StandardFormFieldDto; isBuilder?: boolean }) {
    const { addFieldRatingAnswer, formResponse } = useFormResponse();
    const answer = formResponse.answers && formResponse.answers[field.id]?.number;
    const [hovered, setHovered] = useState(-1);

    const form = useAppSelector(selectForm);
    const { currentSlide } = useResponderState();

    const { theme } = useFormState();
    const steps = field.properties?.steps || 5;
    const RatingSection = () => {
        return (
            <div className="relative !mb-0 flex w-fit  flex-wrap gap-3">
                {_.range(steps).map((index) => {
                    return (
                        <button
                            type="button"
                            aria-label={`Rate ${index + 1} of ${steps}`}
                            aria-pressed={index <= (answer ?? 0) - 1}
                            key={index}
                            disabled={isBuilder}
                            onMouseOut={() => {
                                if (!isBuilder) setHovered(-1);
                            }}
                            onClick={() => {
                                if (!isBuilder) {
                                    addFieldRatingAnswer(field.id, index + 1);
                                    setTimeout(() => {
                                        if (form?.fields?.[currentSlide]?.properties?.fields?.length !== field.index + 1) scrollToDivById(form?.fields?.[currentSlide]?.properties?.fields?.[field.index + 1]?.id);
                                    }, 200);
                                }
                            }}
                            className="cursor-pointer rounded outline-none focus-visible:ring-2"
                            onMouseOver={() => {
                                if (!isBuilder) setHovered(index);
                            }}
                        >
                            {/* Hover previews per star (up to the hovered one); empty stars
                                are TRANSPARENT so they read as outlines on any ground —
                                accent-filled stars became opaque boxes over the new
                                gradient/pattern/image backgrounds. The old group-level
                                mouseOver recolour flipped the whole row at once. */}
                            <StarIcon fill={index <= hovered ? theme?.tertiary : index <= (answer ?? 0) - 1 && hovered < 0 ? theme?.secondary : 'transparent'} stroke={theme?.secondary} />
                        </button>
                    );
                })}
            </div>
        );
    };
    return (
        <>
            {isBuilder ? (
                <RatingSection />
            ) : (
                <QuestionWrapper field={field}>
                    <RatingSection />
                </QuestionWrapper>
            )}
        </>
    );
}
