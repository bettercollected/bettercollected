import { CSSProperties } from 'react';

import _ from 'lodash';

import { FormTheme } from '@app/constants/theme';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { moveOnFrom } from '@app/utils/scroll-utils';
import { cn } from '@app/shadcn/util/lib';
import { themed } from '@app/views/molecules/theme/theme-root';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';

import { useQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

/**
 * One number of the scale. The chosen one is filled with the theme's
 * highlight where it sets one (theme-root.ts), else the action colour; its
 * edge takes the highlight's edge colour, which keeps 3:1 on the page (the
 * ink for a light highlight), as option cards do.
 */
export function scaleCellStyle(colours: Partial<FormTheme> | undefined, selected: boolean, radius: string): CSSProperties {
    return {
        ['--scale-edge' as string]: selected ? themed('--form-highlight-edge', colours?.secondary) : colours?.tertiary,
        ['--scale-edge-hover' as string]: selected ? themed('--form-highlight-edge', colours?.secondary) : colours?.primary,
        background: selected ? themed('--form-highlight-solid', colours?.secondary) : '#ffffff',
        color: selected ? 'var(--form-highlight-solid-ink, #ffffff)' : colours?.primary,
        borderRadius: radius
    };
}

const LinearRatingSection = ({ field, slide, isBuilder = false }: { field: StandardFormFieldDto; slide?: StandardFormFieldDto; isBuilder?: boolean }) => {
    const { theme } = useFormState();
    const { formResponse, addFieldLinearRatingAnswer } = useFormResponse();
    const answer = formResponse.answers && formResponse.answers[field.id]?.number;
    const form = useAppSelector(selectForm);
    const { currentSlide } = useResponderState();

    // A slide-level theme (when present) wins over the form theme.
    const colours = slide?.properties?.theme?.secondary ? slide.properties.theme : theme;
    const tokens = styleTokens(theme?.style);
    // Named by the question (empty on the builder canvas, which has no wrapper).
    const { group, label } = useQuestionLabel();

    return (
        // Square 48px cells: a comfortable touch target, numbers in the
        // theme's ink on a white face, the theme's border at rest (3:1 on its
        // ground), ink on hover, and the chosen number filled with the action
        // colour in semibold white, so the choice reads without colour too.
        <div className="flex flex-row flex-wrap gap-2" {...(label ? { role: 'group', ...group } : {})}>
            {_.range(field.properties?.startFrom ?? 1, +(field.properties?.steps ?? 10) + 1, 1).map((index) => {
                const selected = answer === index;
                return (
                    <button
                        type="button"
                        aria-label={`${index}`}
                        aria-pressed={selected}
                        disabled={isBuilder}
                        style={scaleCellStyle(colours, selected, tokens.cardRadius)}
                        key={index}
                        onClick={() => {
                            if (!isBuilder) {
                                addFieldLinearRatingAnswer(field.id, index);
                                setTimeout(() => {
                                    if (form?.fields?.[currentSlide]?.properties?.fields?.length !== field.index + 1) moveOnFrom(field.id, form?.fields?.[currentSlide]?.properties?.fields?.[field.index + 1]?.id);
                                }, 200);
                            }
                        }}
                        className={cn(
                            'flex h-12 w-12 cursor-pointer items-center justify-center border border-(--scale-edge) text-base tabular-nums transition-colors duration-150 enabled:hover:border-(--scale-edge-hover) disabled:cursor-default',
                            selected ? 'font-semibold' : 'font-normal'
                        )}
                    >
                        <span>{index}</span>
                    </button>
                );
            })}
        </div>
    );
};

const LinearRatingField = ({ field, slide, isBuilder = false }: { field: StandardFormFieldDto; slide?: StandardFormFieldDto; isBuilder?: boolean }) => {
    return isBuilder ? (
        <LinearRatingSection field={field} slide={slide} isBuilder={isBuilder}></LinearRatingSection>
    ) : (
        <QuestionWrapper field={field}>
            <LinearRatingSection field={field} slide={slide} isBuilder={isBuilder}></LinearRatingSection>
        </QuestionWrapper>
    );
};

export default LinearRatingField;
