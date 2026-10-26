import { useState } from 'react';

import _ from 'lodash';

import { StarIcon } from '@Components/icons/start';
import { Check } from 'lucide-react';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { moveOnFrom } from '@app/utils/scroll-utils';
import ScaleRadioGroup from '@app/views/atoms/scale-radio-group';
import useJustChosen from '@app/views/atoms/use-just-chosen';
import { themed } from '@app/views/molecules/theme/theme-root';

import { WithQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

/** One star: its fill follows the rating, and the star just chosen settles in (never on mount, never under reduced motion). */
function Star({ checked, fill, stroke }: { checked: boolean; fill?: string; stroke?: string }) {
    const justChosen = useJustChosen(checked);
    return (
        <span className={justChosen ? 'form-star-settle flex' : 'flex'}>
            <StarIcon width={40} height={39} fill={fill} stroke={stroke} />
        </span>
    );
}

/**
 * The answer in words and a mark as well as in fill, so the rating reads
 * without colour; the radios already say it to a screen reader. The line is
 * always there (empty until the first answer), so answering never shifts the
 * page. The mark grows in on the first answer only.
 */
function RatingReadout({ answer, steps, colour, ink }: { answer?: number; steps: number; colour?: string; ink?: string }) {
    const { t } = useRespondentLanguage();
    const justAnswered = useJustChosen(!!answer);
    return (
        <p aria-hidden="true" data-rating-readout className="flex h-[18px] items-center gap-1.5 text-[13px] leading-snug tabular-nums" style={{ color: ink }}>
            {answer ? (
                <>
                    <Check className={justAnswered ? 'form-choice-pop h-4 w-4 shrink-0' : 'h-4 w-4 shrink-0'} strokeWidth={2.5} style={{ color: colour }} />
                    {t('FIELD.RATED', { value: answer, total: steps })}
                </>
            ) : null}
        </p>
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
        <div className="flex w-fit flex-col gap-1">
            {/* A radio group (one tab stop; arrows, Home, End and the digits
                choose): a rating is one answer, not a row of toggles. Choosing
                by key does not move on, so the respondent can still adjust. */}
            {/* Named by the question (empty on the builder canvas, which has no wrapper). */}
            <WithQuestionLabel>
                {({ control }) => (
                    <ScaleRadioGroup
                        values={_.range(1, steps + 1)}
                        value={answer ?? null}
                        disabled={isBuilder}
                        labelProps={control}
                        className="relative mb-0! flex w-fit flex-wrap gap-1"
                        onChange={(value, { viaKeys }) => {
                            if (isBuilder) return;
                            addFieldRatingAnswer(field.id, value);
                            // The preview under a resting pointer would otherwise show the old rating.
                            setHovered(-1);
                            if (viaKeys) return;
                            setTimeout(() => {
                                if (form?.fields?.[currentSlide]?.properties?.fields?.length !== field.index + 1) moveOnFrom(field.id, form?.fields?.[currentSlide]?.properties?.fields?.[field.index + 1]?.id);
                            }, 200);
                        }}
                    >
                        {(value, cell, { checked }) => {
                            const index = value - 1;
                            return (
                                <button
                                    key={value}
                                    {...cell}
                                    type="button"
                                    aria-label={t('FIELD.RATE', { value, total: steps })}
                                    disabled={isBuilder}
                                    onMouseOut={() => {
                                        if (!isBuilder) setHovered(-1);
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
                                    <Star checked={checked} fill={index <= shownUpTo ? theme?.secondary : 'transparent'} stroke={theme?.secondary} />
                                </button>
                            );
                        }}
                    </ScaleRadioGroup>
                )}
            </WithQuestionLabel>
            {!isBuilder && <RatingReadout answer={answer} steps={steps} colour={themed('--form-highlight-edge', theme?.secondary)} ink={theme?.primary} />}
        </div>
    );
    return <>{isBuilder ? ratingSection : <QuestionWrapper field={field}>{ratingSection}</QuestionWrapper>}</>;
}
