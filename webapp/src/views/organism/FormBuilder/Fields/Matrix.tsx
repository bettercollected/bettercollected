import { FormTheme } from '@app/constants/theme';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { IThemeState, useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { Close } from '@app/views/atoms/Icons/Close';
import { TextareaAutosize } from '@mui/material';
import * as CheckboxPrimitive from '@radix-ui/react-checkbox';
import * as RadioGroupPrimitive from '@radix-ui/react-radio-group';
import { Check, Circle } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import styled from 'styled-components';
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
        <div className="flex w-full flex-col overflow-x-auto pb-2">
            <div
                className="grid"
                style={{
                    gridTemplateColumns: `repeat(${(field?.properties?.fields?.[0]?.properties?.choices?.length || 0) + 1} ,minmax(120px,1fr))`
                }}
            >
                <div
                    className="sticky left-0 z-10 -mt-1 w-full opacity-100"
                    style={{
                        background: theme?.accent
                    }}
                ></div>
                {(field?.properties?.fields?.length || -1) > 0 &&
                    field?.properties?.fields?.[0]?.properties?.choices?.map((choice, index) => {
                        return (
                            <div
                                className={cn(
                                    'relative flex max-h-[150px] w-full flex-col items-center justify-center overflow-auto border-[1px] border-t-[2px]  bg-opacity-20 p-2',
                                    index === 0 && 'rounded-tl-lg border-l-[2px]',
                                    field?.properties?.fields?.[0]?.properties?.choices?.length === index + 1 && 'rounded-tr-lg border-r-[2px]'
                                )}
                                key={choice?.id}
                                style={{
                                    borderColor: borderColor,
                                    background: bgColor + '55',
                                    color: borderColor
                                }}
                            >
                                {disabled ? (
                                    <MatrixHeaderInput
                                        disabled={!disabled}
                                        value={choice?.value ?? `Column ${index + 1}`}
                                        placeholder={`Column ${index + 1}`}
                                        onChange={(value: string) => {
                                            if (field.id === activeField?.id) updateColumnTitle(index, value);
                                        }}
                                    />
                                ) : (
                                    <div className="max-h-full max-w-full text-clip break-all text-center text-sm">{choice?.value || `Column ${index + 1}`}</div>
                                )}

                                {disabled && activeField?.id === field.id && (
                                    <div
                                        className="cross-left absolute top-1 rounded-full bg-white p-1 opacity-50"
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

            {field?.properties?.fields?.map((row: StandardFormFieldDto, index) => {
                return (
                    <RadioGroup
                        className="grid w-fit min-w-full"
                        style={{
                            gridTemplateColumns: `repeat(${(field?.properties?.fields?.[0]?.properties?.choices?.length || 0) + 1} ,minmax(120px,1fr))`
                        }}
                        onValueChange={(value) => {
                            addFieldChoiceAnswer(row.id, value);
                        }}
                        value={formResponse?.answers[row.id]?.choice?.value}
                        key={row?.id}
                    >
                        <div className="sticky left-0" style={{ background: theme?.accent }}>
                            <div
                                style={{
                                    borderColor: borderColor,
                                    background: bgColor + '55',
                                    color: borderColor,
                                    opacity: 1
                                }}
                                className={cn(
                                    'relative z-[40000] flex max-h-[150px] w-full flex-col items-center justify-center overflow-auto border-[1px] border-l-[2px] p-2',
                                    index === 0 && 'rounded-tl-lg border-t-[2px]',
                                    field?.properties?.fields?.length === index + 1 && 'rounded-bl-lg border-b-[2px]'
                                )}
                            >
                                {disabled ? (
                                    <MatrixHeaderInput
                                        disabled={!disabled}
                                        value={row?.title?.toString() ?? `Row ${index + 1}`}
                                        placeholder={`Row ${index + 1}`}
                                        onChange={(value: string) => {
                                            if (activeField?.id === field.id) updateRowTitle(index, value);
                                        }}
                                    />
                                ) : (
                                    <div className="max-h-full max-w-full text-clip break-all text-center text-sm">{row?.title?.toString() || `Row ${index + 1}`}</div>
                                )}
                                {disabled && activeField?.id === field.id && (field?.properties?.fields?.length || -1) > 1 && (
                                    <div
                                        className="cross-top absolute left-1 rounded-full bg-white p-1 opacity-50"
                                        onClick={() => {
                                            deleteRow(index);
                                        }}
                                    >
                                        <Close className="h-4 w-4" />
                                    </div>
                                )}
                            </div>
                        </div>
                        {row?.properties?.choices?.map((choice: any, index: number) => {
                            return (
                                <div
                                    style={{
                                        borderColor: borderColor
                                    }}
                                    className={cn(
                                        'flex h-full  flex-col items-center justify-center border-[1px] border-gray-200',
                                        index + 1 === row?.properties?.choices?.length && 'border-r-[2px]',
                                        row!.index + 1 === field?.properties?.fields?.length && 'border-b-[2px]'
                                    )}
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

const MatrixHeaderInput = ({ value, onChange, disabled, placeholder }: { value: string; onChange?: (value: string) => void; disabled?: boolean; placeholder?: string }) => {
    const [inputVal, setInputVal] = useState(value);

    const [debouncedInputValue] = useDebounceValue(inputVal, 300);
    useEffect(() => {
        onChange && onChange(debouncedInputValue);
    }, [debouncedInputValue]);

    useEffect(() => {
        if (value !== inputVal) setInputVal(value);
    }, [value]);

    return (
        <StyledMatrixHeaderInput
            className={cn('ring-none focus:ring-none items-center border-none bg-transparent text-center text-sm outline-none focus:border-none focus:outline-none focus-visible:outline-none active:outline-none', disabled && 'pointer-events-none')}
            placeholder={placeholder || 'Header'}
            value={inputVal}
            onChange={(event) => {
                if (!disabled) setInputVal(event.target.value);
            }}
        />
    );
};
const StyledMatrixHeaderInput = styled(TextareaAutosize)<{ $theme?: IThemeState }>(() => {
    const { theme } = useFormState();
    const themeColor = theme?.tertiary;
    const secondaryColor = theme?.secondary;
    return {
        resize: 'none',
        overflow: 'auto',
        width: '100%',
        '&::placeholder': {
            color: secondaryColor
        },
        '&:focus::placeholder': {
            color: themeColor
        }
    };
});

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
        className={cn('h-5 w-5 rounded border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed', className)}
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
                'text-primary border-primary ring-offset-background focus-visible:ring-ring flex aspect-square !h-7 !w-7 flex-col items-center justify-center rounded-full !border focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed',
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
                <Circle className="h-5 w-5 fill-current text-current" />
            </RadioGroupPrimitive.Indicator>
        </RadioGroupPrimitive.Item>
    );
});
RadioGroupItem.displayName = RadioGroupPrimitive.Item.displayName;

const MatrixField = React.memo(MatrixFieldComponent, (prev, next) => {
    return prev.field === next.field;
});
export default MatrixField;
