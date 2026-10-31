'use client';

import * as React from 'react';

import { ChevronDown } from 'lucide-react';

import useFormContentLanguage from '@app/lib/hooks/use-form-content-language';
import { offeredChoices, useOptionStates } from '@app/lib/hooks/use-option-states';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@app/shadcn/components/ui/collapsible';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useGroupItemScope } from '@app/store/jotai/group-item-scope';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { READ_ONLY_EMPTY } from '@app/utils/form-utils';
import { moveOnFrom } from '@app/utils/scroll-utils';
import Choice from '@app/views/atoms/choice';
import { inputTextOf } from '@app/views/molecules/theme/theme-root';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';

import OptionClearedNotice from './option-cleared-notice';
import { WithQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

export default function DropDownField({ field, slideIndex }: { field: StandardFormFieldDto; slideIndex: number }) {
    const [isOpen, setIsOpen] = React.useState(false);
    const { theme } = useFormState();
    const { t } = useRespondentLanguage();
    const contentLang = useFormContentLanguage();
    const { addFieldChoiceAnswer, formResponse } = useFormResponse();
    // Only the options the form's option logic offers now (utils/option-logic.ts).
    const optionStates = useOptionStates();
    const inGroup = !!useGroupItemScope();

    const form = useAppSelector(selectForm);
    const { currentSlide } = useResponderState();

    const getSelectedValue = () => {
        if (!formResponse.answers) {
            return null;
        }
        const selectedChoiceId = formResponse?.answers[field.id]?.choice?.value;
        const choice = field?.properties?.choices?.find((choice) => choice.id === selectedChoiceId);
        const choiceIndex = field?.properties?.choices?.findIndex((choice) => choice.id === selectedChoiceId);

        function getChoiceValue() {
            return choice?.value ? choice?.value : `Item ${(choiceIndex ?? 0) + 1}`;
        }

        return selectedChoiceId ? getChoiceValue() : '';
    };

    const choiceValue = getSelectedValue();
    const selectedChoiceId = formResponse?.answers?.[field.id]?.choice?.value;
    const tokens = styleTokens(theme?.style);
    const valueId = `dropdown-value-${field.id}`;

    const handleClick = (choiceId: string) => {
        addFieldChoiceAnswer(field.id, choiceId);
        setIsOpen(false);
        setTimeout(() => {
            if (form?.fields?.[currentSlide]?.properties?.fields?.length !== field.index + 1) moveOnFrom(field.id, form?.fields?.[currentSlide]?.properties?.fields?.[field.index + 1]?.id);
        }, 200);
    };

    const getTextStyle = () => {
        if (choiceValue) {
            return {
                borderColor: theme?.secondary,
                // The chosen answer is content — ink (or the theme's input text), not the action colour.
                color: inputTextOf(theme)
            };
        }
        // Placeholder state: the theme's border colour (3:1 on its ground),
        // legible neutral text.
        return { borderColor: theme?.tertiary || '#818CA0', color: '#667085' };
    };

    return (
        <QuestionWrapper field={field}>
            <WithQuestionLabel hints={[valueId]}>
                {({ label, group }) => (
                    <Collapsible open={isOpen} onOpenChange={setIsOpen} className="space-y-2">
                        <CollapsibleTrigger asChild>
                            {/* Same input language as every other field: bordered white
                                rounded-md box, base/lg type, real button semantics — the old
                                trigger was a text-3xl underline-only div with no keyboard
                                affordance, a different species from the rest of the form. */}
                            <button
                                type="button"
                                // Named by the question; the chosen answer (or "Select an option") describes it.
                                aria-labelledby={label?.labelledBy}
                                aria-describedby={group['aria-describedby']}
                                // Locked by a field rule: a read-only combobox (a button has no read-only state); the wrapper keeps it from opening.
                                {...(label?.readOnly ? { role: 'combobox', 'aria-readonly': true } : {})}
                                style={{ ...getTextStyle(), borderRadius: tokens.fieldRadius, ['--hover-border' as string]: theme?.primary ?? '#101828' }}
                                className="flex min-h-12 w-full cursor-pointer items-center justify-between gap-4 border bg-white px-4 py-3 text-left text-base transition duration-150 hover:border-(--hover-border)! lg:text-lg"
                            >
                                <span id={valueId} className="truncate" lang={choiceValue ? contentLang : undefined}>
                                    {choiceValue ? choiceValue : label?.readOnly ? <span aria-hidden="true">{READ_ONLY_EMPTY}</span> : t('FIELD.SELECT_OPTION')}
                                </span>
                                <ChevronDown aria-hidden="true" className={`h-5 w-5 shrink-0 transition ${isOpen ? 'rotate-180' : ''}`} style={{ color: theme?.secondary }} />
                            </button>
                        </CollapsibleTrigger>
                        <CollapsibleContent className={tokens.ruledChoices ? '' : 'space-y-2'}>
                            {offeredChoices(field.properties?.choices, field.id, optionStates, inGroup).map(({ choice, index }) => {
                                return <Choice key={choice.id} index={index} isSelected={!!selectedChoiceId && choice.id === selectedChoiceId} theme={theme} choice={choice} onClick={handleClick} lang={contentLang} />;
                            })}
                        </CollapsibleContent>
                        {!inGroup && <OptionClearedNotice fieldId={field.id} />}
                    </Collapsible>
                )}
            </WithQuestionLabel>
        </QuestionWrapper>
    );
}
