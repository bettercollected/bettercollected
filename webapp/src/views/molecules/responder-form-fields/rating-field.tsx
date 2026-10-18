import { useState } from 'react';

import _ from 'lodash';

import { StarIcon } from '@Components/icons/start';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { scrollToDivById } from '@app/utils/scroll-utils';

import { useQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

/** The stars, as a group named by the question they answer. */
function RatingGroup({ children }: { children: React.ReactNode }) {
    const { group, label } = useQuestionLabel();
    return (
        <div className="relative mb-0! flex w-fit flex-wrap gap-1" {...(label ? { role: 'group', ...group } : {})}>
            {children}
        </div>
    );
}

export default function RatingField({ field, slide, isBuilder = false }: { field: StandardFormFieldDto; slide?: StandardFormFieldDto; isBuilder?: boolean }) {
    const { addFieldRatingAnswer, formResponse } = useFormResponse();
    const answer = formResponse.answers && formResponse.answers[field.id]?.number;
    const [hovered, setHovered] = useState(-1);
    const { t } = useRespondentLanguage();

    const form = useAppSelector(selectForm);
    const { currentSlide } = useResponderState();

    const { theme } = useFormState();
    const steps = field.properties?.steps || 5;
    // Stars up to the hovered one preview the rating; otherwise the answer shows.
    const shownUpTo = hovered >= 0 ? hovered : (answer ?? 0) - 1;
    // A plain element, not a component declared in render: a nested component
    // is a new type on every render, so each hover remounted every star — the
    // click could land on a detached button and keyboard focus was lost.
    const ratingSection = (
        <RatingGroup>
            {_.range(steps).map((index) => {
                return (
                    <button
                        type="button"
                        aria-label={t('FIELD.RATE', { value: index + 1, total: steps })}
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
                        className="flex h-12 w-12 cursor-pointer items-center justify-center rounded-[4px] disabled:cursor-default"
                        onMouseOver={() => {
                            if (!isBuilder) setHovered(index);
                        }}
                    >
                        {/* Hover previews per star (up to the hovered one) in the same
                            accent as the answer, so the rating just clicked shows while
                            the pointer is still on it (a pale preview hid it). Empty stars
                            are TRANSPARENT so they read as outlines on any ground. */}
                        <StarIcon width={40} height={39} fill={index <= shownUpTo ? theme?.secondary : 'transparent'} stroke={theme?.secondary} />
                    </button>
                );
            })}
        </RatingGroup>
    );
    return <>{isBuilder ? ratingSection : <QuestionWrapper field={field}>{ratingSection}</QuestionWrapper>}</>;
}
