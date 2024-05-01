import { FormTheme } from '@app/constants/theme';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { Close } from '@app/views/atoms/Icons/Close';
import { TextareaAutosize } from '@mui/material';
import * as CheckboxPrimitive from '@radix-ui/react-checkbox';
import * as RadioGroupPrimitive from '@radix-ui/react-radio-group';
import { Check, Circle } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { useDebounceValue } from 'usehooks-ts';

interface IMatrixFieldProps {
    field: StandardFormFieldDto;
    disabled?: boolean;
}

function MatrixFieldComponent({ field, disabled }: IMatrixFieldProps) {
    const { theme } = useFormState();

    const { addFieldChoicesAnswer, addFieldChoiceAnswer, formResponse } = useFormResponse();

    const borderColor = theme?.secondary;
    const bgColor = theme?.tertiary;

    const { updateRowTitle, updateColumnTitle, activeField, deleteColumn, deleteRow } = useFormFieldsAtom();

    return (
        <div className="flex flex-col">
            <div
                className="grid"
                style={{
                    gridTemplateColumns: `repeat(${(field?.properties?.fields?.[0]?.properties?.choices?.length || 0) + 1} ,minmax(0,1fr))`
                }}
            >
                <div></div>
                {(field?.properties?.fields?.length || -1) > 0 &&
                    field?.properties?.fields?.[0]?.properties?.choices?.map((choice, index) => {
                        return (
                            <div
                                className={cn('w-ful relative flex flex-col items-center  border-[1px]  p-3', index === 0 && 'rounded-tl-lg', field?.properties?.fields?.[0]?.properties?.choices?.length === index + 1 && 'rounded-tr-lg')}
                                key={choice?.id}
                                style={{
                                    borderColor: borderColor,
                                    background: bgColor,
                                    color: borderColor
                                }}
                            >
                                {disabled ? (
                                    <MatrixHeaderInput
                                        disabled={!disabled}
                                        value={choice?.value ?? `Column ${index}`}
                                        onChange={(value: string) => {
                                            if (field.id === activeField?.id) updateColumnTitle(index, value);
                                        }}
                                    />
                                ) : (
                                    <div className="py-2 text-center">{choice?.value ?? `Column ${index}`}</div>
                                )}

                                {disabled && activeField?.id === field.id && (
                                    <div
                                        className="absolute left-1 top-1 rounded-full bg-white p-1 opacity-50"
                                        onClick={() => {
                                            deleteColumn(index);
                                        }}
                                    >
                                        <Close className="h-4 w-4" />
                                    </div>
                                )}
                            </div>
                        );
                    })}
            </div>

            {field?.properties?.fields?.map((row: any, index) => {
                return (
                    <RadioGroup
                        className="grid"
                        style={{
                            gridTemplateColumns: `repeat(${(field?.properties?.fields?.[0]?.properties?.choices?.length || 0) + 1} ,minmax(0,1fr))`
                        }}
                        onValueChange={(value) => {
                            addFieldChoiceAnswer(row.id, value);
                        }}
                        value={formResponse?.answers[row.id]?.choice?.value}
                        key={row?.id}
                    >
                        <div
                            style={{
                                borderColor: borderColor,
                                background: bgColor,
                                color: borderColor
                            }}
                            className={cn('relative flex w-full flex-col items-center border-[1px] p-2 px-4', index === 0 && 'rounded-tl-lg', field?.properties?.fields?.length === index + 1 && 'rounded-bl-lg')}
                        >
                            {disabled ? (
                                <MatrixHeaderInput
                                    disabled={!disabled}
                                    value={row?.title?.toString() ?? `Row ${index}`}
                                    onChange={(value: string) => {
                                        if (activeField?.id === field.id) updateRowTitle(index, value);
                                    }}
                                />
                            ) : (
                                <div className="py-2 text-center">{row?.title?.toString() ?? `Row ${index}`}</div>
                            )}
                            {disabled && activeField?.id === field.id && (field?.properties?.fields?.length || -1) > 1 && (
                                <div
                                    className="absolute left-2 top-2 rounded-full bg-white p-1 opacity-50"
                                    onClick={() => {
                                        deleteRow(index);
                                    }}
                                >
                                    <Close className="h-4 w-4" />
                                </div>
                            )}
                        </div>
                        {row?.properties?.choices?.map((choice: any, index: number) => {
                            return (
                                <div
                                    style={{
                                        borderColor: borderColor
                                    }}
                                    className="flex h-full  flex-col items-center justify-center border-[1px] border-gray-200"
                                    key={index}
                                >
                                    {field.properties?.allowMultipleSelection ? (
                                        <MatrixCheckbox
                                            checked={formResponse.answers[row.id]?.choices?.values?.includes(choice?.id)}
                                            onCheckedChange={(checked) => {
                                                let choices;
                                                if (checked) {
                                                    choices = formResponse.answers[row.id]?.choices?.values || [];
                                                    choices.push(choice.id);
                                                } else {
                                                    choices = (formResponse.answers[row.id]?.choices?.values || []).filter((choiceId) => choiceId !== choice.id);
                                                }
                                                addFieldChoicesAnswer(row.id, choices);
                                            }}
                                            theme={theme}
                                            disabled={disabled}
                                        />
                                    ) : (
                                        <RadioGroupItem value={choice.id} theme={theme} className="h-full" disabled={disabled} />
                                    )}
                                </div>
                            );
                        })}
                    </RadioGroup>
                );
            })}
        </div>
    );
}

const MatrixHeaderInput = ({ value, onChange, disabled }: { value: string; onChange?: (value: string) => void; disabled?: boolean }) => {
    const [inputVal, setInputVal] = useState(value);

    const [debouncedInputValue] = useDebounceValue(inputVal, 300);
    useEffect(() => {
        onChange && onChange(debouncedInputValue);
    }, [debouncedInputValue]);

    useEffect(() => {
        if (value !== inputVal) setInputVal(value);
    }, [value]);

    return (
        <TextareaAutosize
            style={{ resize: 'none' }}
            className={cn('ring-none focus:ring-none border-none bg-transparent text-center text-sm outline-none focus:border-none focus:outline-none focus-visible:outline-none active:outline-none', disabled && 'pointer-events-none')}
            placeholder="Header"
            value={inputVal}
            onChange={(event) => {
                if (!disabled) setInputVal(event.target.value);
            }}
        />
    );
};

type MatrixCheckboxProps = React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root> & {
    className?: string;
    theme?: FormTheme; // or whatever type your theme should be
};

const MatrixCheckbox = React.forwardRef<React.ElementRef<typeof CheckboxPrimitive.Root>, MatrixCheckboxProps>(({ className, theme, ...props }, ref) => (
    <CheckboxPrimitive.Root
        ref={ref}
        style={{
            borderColor: theme?.secondary
        }}
        className={cn('h-5 w-5 rounded border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50', className)}
        {...props}
    >
        <CheckboxPrimitive.Indicator
            style={{
                background: theme?.secondary
            }}
            className={cn(' flex h-5 w-5 items-center justify-center rounded')}
        >
            <Check className="text-white" />
        </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
));
MatrixCheckbox.displayName = CheckboxPrimitive.Root.displayName;

type RadioGroupProps = React.ComponentPropsWithoutRef<typeof RadioGroupPrimitive.Root> & {
    className?: string;
    theme?: FormTheme; // or whatever type your theme should be
};

const RadioGroup = React.forwardRef<React.ElementRef<typeof RadioGroupPrimitive.Root>, RadioGroupProps>(({ className, theme, ...props }, ref) => {
    return <RadioGroupPrimitive.Root className={cn('', className)} {...props} ref={ref} />;
});
RadioGroup.displayName = RadioGroupPrimitive.Root.displayName;

type RadioGroupItemProps = React.ComponentPropsWithoutRef<typeof RadioGroupPrimitive.Item> & {
    className?: string;
    theme?: FormTheme; // or whatever type your theme should be
};

const RadioGroupItem = React.forwardRef<React.ElementRef<typeof RadioGroupPrimitive.Item>, RadioGroupItemProps>(({ className, theme, ...props }, ref) => {
    return (
        <RadioGroupPrimitive.Item
            ref={ref}
            className={cn(
                'text-primary border-primary ring-offset-background focus-visible:ring-ring flex aspect-square !h-4 !w-4 flex-col items-center justify-center rounded-full !border focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
                className
            )}
            {...props}
            style={{
                border: `solid` + theme?.secondary || '' // Assuming theme.secondary represents the background color
            }}
        >
            <RadioGroupPrimitive.Indicator
                style={{
                    color: theme?.secondary // Assuming theme.secondary represents the background color
                }}
                className={cn('flex items-center justify-center')}
            >
                <Circle className="!h-3 !w-3 fill-current text-current" />
            </RadioGroupPrimitive.Indicator>
        </RadioGroupPrimitive.Item>
    );
});
RadioGroupItem.displayName = RadioGroupPrimitive.Item.displayName;

const MatrixField = React.memo(MatrixFieldComponent, (prev, next) => {
    return prev.field === next.field;
});
export default MatrixField;
