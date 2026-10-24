import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import Choice, { optionIndexForKey, optionKeys, showsOptionKeys } from '@app/views/atoms/choice';
import { KeyboardEvent } from 'react';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';
import { WithQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

import useFormContentLanguage from '@app/lib/hooks/use-form-content-language';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';

export default function MultipleChoiceWithMultipleSelection({ field, slideIndex }: { field: StandardFormFieldDto; slideIndex: number }) {
    const { addFieldChoicesAnswer, addOtherChoicesAnswer, formResponse, removeAnswer } = useFormResponse();

    const { theme } = useFormState();
    const { t } = useRespondentLanguage();
    const contentLang = useFormContentLanguage();
    const tokens = styleTokens(theme?.style);

    const standardForm = useAppSelector(selectForm);
    const currentSlide = standardForm.fields![slideIndex];

    const getSelectedValues = () => {
        if (!formResponse.answers) {
            return null;
        }
        return formResponse?.answers[field.id]?.choices?.values || [];
    };

    const selectedValues = getSelectedValues() || [];

    const otherOption = formResponse?.answers?.[field.id]?.choices?.other || '';

    const handleClick = (choiceId: string) => {
        const index = selectedValues.indexOf(choiceId);

        if (index === -1) {
            selectedValues.push(choiceId);
        } else {
            selectedValues.splice(index, 1);
        }
        selectedValues.length ? addFieldChoicesAnswer(field.id, selectedValues) : removeAnswer(field.id);
    };

    // On a theme that shows option keys, each option carries its letter, and
    // pressing one while an option has focus ticks or unticks that option and
    // moves focus to it.
    const keys = showsOptionKeys(theme) ? optionKeys(field.properties?.choices?.length ?? 0) : [];
    const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
        const index = optionIndexForKey(event, keys);
        if (index < 0) return;
        event.preventDefault();
        const option = event.currentTarget.parentElement?.querySelector<HTMLButtonElement>(`[data-option-key="${keys[index]}"]`);
        option?.focus();
        option?.click();
    };

    return (
        <QuestionWrapper field={field}>
            <div className="w-full space-y-2 p-0">
                {/* A hint, not a heading: it tells the respondent this one
                    takes several answers (the controls are checkboxes too). */}
                <p id={`choose-many-${field.id}`} style={{ color: currentSlide?.properties?.theme?.primary || theme?.primary }} className="text-[13px] leading-snug opacity-90">
                    {t('FIELD.CHOOSE_MANY')}
                </p>
                {/* The checkboxes are a group named by the question and
                    described by it, then by the hint, as they read on screen. */}
                <WithQuestionLabel hints={[`choose-many-${field.id}`]}>
                    {({ group }) => (
                        <div role="group" {...group} className={tokens.ruledChoices ? '' : 'space-y-2'}>
                            {field.properties?.choices?.map((choice, index) => {
                                const isSelected = selectedValues.includes(choice.id);
                                return <Choice key={choice.id} kind="checkbox" isSelected={isSelected} theme={theme} choice={choice} onClick={handleClick} index={index} lang={contentLang} keyHint={keys[index]} onKeyDown={onKeyDown} />;
                            })}
                        </div>
                    )}
                </WithQuestionLabel>
                {field?.properties?.allowOtherChoice && (
                    <FieldInput
                        type="text"
                        value={otherOption}
                        placeholder={t('FIELD.OTHER_CHOICE')}
                        aria-label={t('FIELD.OTHER')}
                        onChange={(e: any) => {
                            if (!e.target.value && !formResponse.answers[field.id]) {
                                removeAnswer(field.id);
                                return;
                            }
                            addOtherChoicesAnswer(field.id, e.target.value);
                        }}
                        $formTheme={theme}
                        className="flex min-h-12 justify-between border px-4 py-3 text-base"
                    />
                )}
            </div>
        </QuestionWrapper>
    );
}
