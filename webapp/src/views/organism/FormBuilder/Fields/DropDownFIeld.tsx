import { FieldTypes, FormField } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { ArrowDown } from '@app/views/atoms/Icons/ArrowDown';
import { PlusIcon } from '@app/views/atoms/Icons/Plus';
import { useState } from 'react';

const DropDownField = ({ field, slide, disabled }: { field: FormField; slide: FormField; disabled: boolean }) => {
    const { updateChoiceFieldValue, addChoiceField, removeChoiceField } = useFormFieldsAtom();
    const { theme } = useFormState();
    const [backspaceCount, setBackspaceCount] = useState(0);
    return (
        <>
            {field.type === FieldTypes.DROP_DOWN ? (
                <div
                    style={{
                        borderColor: slide.properties?.theme?.tertiary || theme?.tertiary,
                        color: slide.properties?.theme?.tertiary || theme?.tertiary
                    }}
                    className="mb-2 flex w-full items-center justify-between border-0 border-b-[1px] py-2 text-3xl "
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
                    <h1
                        style={{
                            color: slide.properties?.theme?.secondary || theme?.secondary
                        }}
                        className="-mt-1 mb-1 font-medium"
                    >
                        Choose as many as you like
                    </h1>
                )
            )}
            <div className={'flex w-full flex-col gap-2'}>
                {field &&
                    field.properties?.choices?.map((choice, index) => {
                        return (
                            <FieldInput
                                onKeyDown={(e) => {
                                    if (e.key === 'Backspace') {
                                        setBackspaceCount(backspaceCount + 1);
                                    }
                                    if (e.key === 'Backspace' && backspaceCount == 1 && !choice.value) {
                                        console.log(choice.id);
                                        removeChoiceField(field.index, slide.index, choice.id);
                                        setBackspaceCount(0);
                                    }
                                }}
                                onFocus={() => setBackspaceCount(0)}
                                $slide={slide}
                                type="text"
                                $formTheme={theme}
                                textColor={slide.properties?.theme?.secondary || theme?.secondary || 'text-black-500'}
                                value={choice.value}
                                key={index}
                                placeholder={`Item ${index + 1}`}
                                onChange={(e: any) => updateChoiceFieldValue(field.index, slide.index, choice.id, e.target.value)}
                                className={`flex justify-between rounded-xl border p-2 px-4 text-base`}
                            />
                        );
                    })}
            </div>
            {field?.properties?.allowOtherChoice && (
                <div
                    style={{
                        color: slide.properties?.theme?.tertiary || theme?.tertiary,
                        borderColor: slide.properties?.theme?.tertiary || theme?.tertiary
                    }}
                    className={'flex justify-between rounded-xl border p-2 px-4 text-base'}
                >
                    Other
                </div>
            )}
            <div
                style={{
                    color: slide?.properties?.theme?.secondary || theme?.secondary,
                    background: 'transparent'
                    // background: slide.properties?.theme?.tertiary || theme?.tertiary
                }}
                onClick={() => addChoiceField(field.index, slide.index)}
                className="p2-new mt-4 flex items-center gap-2 !font-semibold"
            >
                <PlusIcon className="h-4 w-4" />
                Add Option
            </div>
        </>
    );
};

export default DropDownField;
