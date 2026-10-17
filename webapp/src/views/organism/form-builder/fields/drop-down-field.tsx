import { Close } from '@app/components/icons/close';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import FieldInputWrapper from '@Components/hocs/field-input-wrapper';
import { ArrowDown } from '@Components/icons/arrow-down';
import { PlusIcon } from 'lucide-react';
import { useState } from 'react';

import { cn } from '@app/shadcn/util/lib';
import { ChoiceIndicator, choiceRowStyle } from '@app/views/atoms/choice';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';

const DropDownField = ({ field, slide, disabled }: { field: StandardFormFieldDto; slide: StandardFormFieldDto; disabled: boolean }) => {
    const { updateChoiceFieldValue, addChoiceField, removeChoiceField } = useFormFieldsAtom();
    const { theme } = useFormState();
    const [backspaceCount, setBackspaceCount] = useState(0);
    const rowTheme = slide.properties?.theme?.secondary ? { ...theme, ...slide.properties.theme } : theme;
    const isChoiceList = field.type === FieldTypes.MULTIPLE_CHOICE;
    return (
        <>
            {field.type === FieldTypes.DROP_DOWN ? (
                <div
                    style={{
                        borderColor: slide.properties?.theme?.tertiary || theme?.tertiary,
                        color: slide.properties?.theme?.tertiary || theme?.tertiary
                    }}
                    className="mb-2 flex w-full items-center justify-between border-0 border-b py-2 text-3xl "
                >
                    <h1>Select an option</h1>
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
                        Choose as many as you like.
                    </p>
                )
            )}
            {/* WYSIWYG: each option wears the respondent's row (control, ruled
                or boxed per style), with the label editable in place. */}
            <div className={cn('flex w-full flex-col', !isChoiceList || !styleTokens(rowTheme?.style).ruledChoices ? 'gap-2' : '')}>
                {field &&
                    field.properties?.choices?.map((choice, index) => {
                        const row = choiceRowStyle(rowTheme, false);
                        const input = (
                            <FieldInputWrapper
                                onFocus={() => setBackspaceCount(0)}
                                value={choice.value}
                                placeholder={`Item ${index + 1}`}
                                onChange={(value: any) => updateChoiceFieldValue(field.index, slide.index, choice.id, value)}
                                className={isChoiceList ? 'min-w-0 flex-1 rounded-none border-0 bg-transparent p-0 text-base' : 'flex justify-between rounded-md border p-2 px-4 text-base'}
                                style={{ color: isChoiceList ? rowTheme?.primary : rowTheme?.secondary }}
                                isOptionsInput
                            />
                        );
                        return (
                            <div className="group relative" key={choice.id ?? index}>
                                {isChoiceList ? (
                                    <div className={cn(row.className, 'cursor-text pr-10')} style={row.style}>
                                        <ChoiceIndicator kind={field.properties?.allowMultipleSelection ? 'checkbox' : 'radio'} theme={rowTheme} />
                                        {input}
                                    </div>
                                ) : (
                                    input
                                )}
                                {/* Hidden until the row is hovered or has focus; opacity, not
                                    visibility, so the button stays reachable by Tab. */}
                                <button
                                    type="button"
                                    aria-label={`Remove option ${index + 1}${choice.value ? `: ${choice.value}` : ''}`}
                                    title="Remove option"
                                    onClick={() => removeChoiceField(field.index, slide.index, choice.id)}
                                    className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center justify-center rounded p-1 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-[#123FC9]"
                                >
                                    <Close style={{ color: theme?.secondary }} aria-hidden="true" className="h-5 w-5" />
                                </button>
                            </div>
                        );
                    })}
            </div>
            {field?.properties?.allowOtherChoice && (
                <div
                    style={{
                        color: slide.properties?.theme?.tertiary || theme?.tertiary,
                        borderColor: slide.properties?.theme?.tertiary || theme?.tertiary
                    }}
                    className={'flex justify-between rounded-md border p-2 px-4 text-base'}
                >
                    Other
                </div>
            )}
            <button
                type="button"
                style={{
                    color: slide?.properties?.theme?.secondary || theme?.secondary,
                    background: 'transparent'
                }}
                onClick={() => addChoiceField(field.index, slide.index)}
                className="p2-new mt-4 flex items-center gap-2 rounded font-semibold! focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#123FC9]"
            >
                <PlusIcon className="h-4 w-4" aria-hidden="true" />
                Add Option
            </button>
        </>
    );
};

export default DropDownField;
