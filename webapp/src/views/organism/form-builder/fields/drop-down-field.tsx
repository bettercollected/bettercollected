import { useEffect, useRef, useState } from 'react';

import FieldInputWrapper from '@Components/hocs/field-input-wrapper';
import { ArrowDown } from '@Components/icons/arrow-down';
import { PlusIcon } from 'lucide-react';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { Close } from '@app/components/icons/close';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { useFieldActions } from '@app/store/jotai/entity-hooks';
import { useBuilderActions } from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { ChoiceIndicator, OptionKeyHint, choiceRowStyle, optionKeys, showsOptionKeys } from '@app/views/atoms/choice';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';

const DropDownField = ({ field, slide, disabled }: { field: StandardFormFieldDto; slide: StandardFormFieldDto; disabled: boolean }) => {
    const { updateChoiceFieldValue } = useFieldActions();
    const { t } = useBuilderTranslation();
    const { t: tr } = useRespondentLanguage();
    const { addChoiceField, removeChoiceField } = useBuilderActions();
    const { theme } = useFormState();
    const [backspaceCount, setBackspaceCount] = useState(0);
    // The option Add Option just made: the cursor goes into it once it shows.
    const [focusChoiceId, setFocusChoiceId] = useState<string | null>(null);
    const listRef = useRef<HTMLDivElement>(null);
    useEffect(() => {
        if (!focusChoiceId) return;
        const inputs = listRef.current?.querySelectorAll<HTMLInputElement>('input[data-choice-id]') ?? [];
        const input = Array.from(inputs).find((element) => element.dataset.choiceId === focusChoiceId);
        if (!input) return;
        input.focus();
        setFocusChoiceId(null);
    }, [focusChoiceId, field.properties?.choices]);
    const rowTheme = slide.properties?.theme?.secondary ? { ...theme, ...slide.properties.theme } : theme;
    const isChoiceList = field.type === FieldTypes.MULTIPLE_CHOICE;
    // The respondent's key letters, on a theme that shows them.
    const keys = isChoiceList && showsOptionKeys(rowTheme) ? optionKeys(field.properties?.choices?.length ?? 0) : [];
    return (
        <>
            {field.type === FieldTypes.DROP_DOWN ? (
                <div
                    style={{
                        borderColor: slide.properties?.theme?.tertiary || theme?.tertiary,
                        color: slide.properties?.theme?.tertiary || theme?.tertiary
                    }}
                    className="mb-2 flex w-full items-center justify-between border-0 border-b py-2 text-3xl"
                >
                    <h1>{tr('FIELD.SELECT_OPTION')}</h1>
                    <ArrowDown
                        style={{
                            color: slide.properties?.theme?.secondary || theme?.secondary
                        }}
                    />
                </div>
            ) : (
                field.properties &&
                field.properties.allowMultipleSelection && (
                    <p style={{ color: rowTheme?.primary }} className="text-[13px] leading-snug opacity-90">
                        {tr('FIELD.CHOOSE_MANY')}
                    </p>
                )
            )}
            {/* WYSIWYG: each option wears the respondent's row (control, ruled
                or boxed per style), with the label editable in place. */}
            <div ref={listRef} className={cn('flex w-full flex-col', !isChoiceList || !styleTokens(rowTheme?.style).ruledChoices ? 'gap-2' : '')}>
                {field &&
                    field.properties?.choices?.map((choice, index) => {
                        const row = choiceRowStyle(rowTheme, false);
                        const input = (
                            <FieldInputWrapper
                                onFocus={() => setBackspaceCount(0)}
                                value={choice.value}
                                placeholder={t('CANVAS.ITEM_N', { n: index + 1 })}
                                onChange={(value: any) => updateChoiceFieldValue(field.id, choice.id, value)}
                                className={isChoiceList ? 'min-w-0 flex-1 rounded-none border-0 bg-transparent p-0 text-base' : 'flex justify-between rounded-md border p-2 px-4 text-base'}
                                style={{ color: isChoiceList ? rowTheme?.primary : rowTheme?.secondary }}
                                isOptionsInput
                                data-choice-id={choice.id}
                            />
                        );
                        return (
                            <div className="group relative" key={choice.id ?? index}>
                                {isChoiceList ? (
                                    <div className={cn(row.className, 'cursor-text pr-10')} style={row.style}>
                                        {keys[index] ? <OptionKeyHint letter={keys[index]!} theme={rowTheme} /> : <ChoiceIndicator kind={field.properties?.allowMultipleSelection ? 'checkbox' : 'radio'} theme={rowTheme} />}
                                        {input}
                                    </div>
                                ) : (
                                    input
                                )}
                                {/* Builder-only note: this option is shown or hidden by answers */}
                                {choice.logic && (
                                    <span data-testid={`option-badge-${choice.id}`} className="pointer-events-none absolute top-1/2 right-10 -translate-y-1/2 rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-medium text-amber-900">
                                        {t('OPTION_LOGIC.BADGE')}
                                    </span>
                                )}
                                {/* Hidden until the row is hovered or has focus; opacity, not
                                    visibility, so the button stays reachable by Tab. */}
                                <button
                                    type="button"
                                    aria-label={choice.value ? t('CANVAS.REMOVE_OPTION_NAMED', { n: index + 1, value: choice.value }) : t('CANVAS.REMOVE_OPTION_N', { n: index + 1 })}
                                    title={t('CANVAS.REMOVE_OPTION')}
                                    onClick={() => removeChoiceField(field.index, slide.index, choice.id)}
                                    className="absolute top-1/2 right-2 flex -translate-y-1/2 items-center justify-center rounded p-1 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-[#123FC9]"
                                >
                                    <Close style={{ color: theme?.secondary }} aria-hidden="true" className="h-5 w-5" />
                                </button>
                            </div>
                        );
                    })}
            </div>
            {field?.properties?.optionFilter && (
                <p data-testid="option-filter-note" className="mt-2 w-fit rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-medium text-amber-900">
                    {t('OPTION_LOGIC.BADGE_FILTERED')}
                </p>
            )}
            {field?.properties?.allowOtherChoice && (
                <div
                    style={{
                        color: slide.properties?.theme?.tertiary || theme?.tertiary,
                        borderColor: slide.properties?.theme?.tertiary || theme?.tertiary
                    }}
                    className={'flex justify-between rounded-md border p-2 px-4 text-base'}
                >
                    {tr('FIELD.OTHER')}
                </div>
            )}
            <button
                type="button"
                style={{
                    color: slide?.properties?.theme?.secondary || theme?.secondary,
                    background: 'transparent'
                }}
                onClick={() => setFocusChoiceId(addChoiceField(field.index, slide.index))}
                className="p2-new mt-4 flex items-center gap-2 rounded font-semibold! focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#123FC9]"
            >
                <PlusIcon className="h-4 w-4" aria-hidden="true" />
                {t('CANVAS.ADD_OPTION')}
            </button>
        </>
    );
};

export default DropDownField;
