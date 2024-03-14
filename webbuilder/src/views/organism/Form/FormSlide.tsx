'use client';

import React, { Fragment, useState } from 'react';

import Image from 'next/image';

import { RadioGroup } from '@headlessui/react';
import parse from 'html-react-parser';

import DemoImage from '@app/assets/image/rectangle.png';
import { FieldTypes, FormField } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import StandardForm, {
    useFormSlide,
    useFormTheme,
    useStandardForm
} from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/getHtmlFromJson';
import { Check } from '@app/views/atoms/Icons/Check';
import RequiredIcon from '@app/views/atoms/Icons/Required';
import { getPlaceholderValueForTitle } from '@app/views/molecules/RichTextEditor';

function QuestionWrapper({
    field,
    children
}: {
    field: FormField;
    children?: React.ReactNode;
}) {
    return (
        <div className="relative flex flex-col">
            {field?.validations?.required && (
                <div className="top- 2 absolute -right-10">
                    <RequiredIcon className="text-red-500" />
                </div>
            )}
            <div className="font-semibold">
                {parse(
                    getHtmlFromJson(field?.title) ??
                        getPlaceholderValueForTitle(field?.type || FieldTypes.TEXT)
                )}
            </div>
            {field?.description && (
                <div className="mt-2 text-black-700">{field?.description}</div>
            )}
            {children}
        </div>
    );
}

function FormFieldComponent({ field, form }: { field: FormField; form: StandardForm }) {
    const theme = useFormTheme();
    const { addFieldTextAnswer, addFieldEmailAnswer, formResponse } = useFormResponse();
    console.log('sda', formResponse);
    switch (field.type) {
        case FieldTypes.TEXT:
            return (
                <div className="h1-new w-full text-left text-[32px] font-bold">
                    {parse(getHtmlFromJson(field?.title) ?? 'No Fields')}
                </div>
            );
        case FieldTypes.EMAIL:
            return (
                <QuestionWrapper field={field}>
                    <FieldInput
                        type="email"
                        placeholder={field?.properties?.placeholder}
                        $slide={field}
                        onChange={(e: any) =>
                            addFieldEmailAnswer(field.id, e.target.value)
                        }
                    />
                </QuestionWrapper>
            );
        case FieldTypes.SHORT_TEXT:
            return (
                <QuestionWrapper field={field}>
                    <FieldInput
                        type="text"
                        placeholder={field?.properties?.placeholder}
                        className="mt-4"
                        onChange={(e: any) =>
                            addFieldTextAnswer(field.id, e.target.value)
                        }
                    />
                </QuestionWrapper>
            );
        case FieldTypes.MULTIPLE_CHOICE:
            return <MultipleChoiceField field={field} />;
        case FieldTypes.YES_NO:
            return <YesNoField field={field} />;

        default:
            return <QuestionWrapper field={field} />;
    }
}

// optional
// const MultipleChoiceField = ({ field }: { field: FormField }) => {
//     const { addFieldChoiceAnswer } = useFormResponse();
//     const theme = useFormTheme();
//     return (
//         <QuestionWrapper field={field}>
//             <select
//                 className="w-full space-y-2 overflow-hidden border-0 p-0"
//                 multiple
//                 onChange={(e) =>
//                     console.log(
//                         e
//                         // Array.from(e.target.selectedOptions).map(
//                         //     (selectedOptions) => selectedOptions.value
//                         // )
//                     )
//                 }
//             >
//                 {field.properties?.choices?.map((choice) => {
//                     return (
//                         <option
//                             style={{ borderColor: theme?.tertiary }}
//                             className="cursor-pointer rounded-xl border p-2 px-4 checked:bg-red-500 hover:bg-black-700 active:bg-yellow-500"
//                             value={choice.value}
//                         >
//                             {choice.value}
//                         </option>
//                     );
//                 })}
//             </select>
//         </QuestionWrapper>
//     );
// };

const MultipleChoiceField = ({ field }: { field: FormField }) => {
    const { addFieldChoicesAnswer } = useFormResponse();
    const theme = useFormTheme();
    const [selectedItems, setSelectedItems] = useState<Array<string>>([]);

    const handleClick = (item: string) => {
        const isSelected = selectedItems.includes(item);
        setSelectedItems((prev) => {
            const updatedSelection = isSelected
                ? selectedItems.filter((selectedItem: string) => selectedItem !== item)
                : [...selectedItems, item];
            addFieldChoicesAnswer(field.id, updatedSelection);
            return updatedSelection;
        });
    };

    return (
        <QuestionWrapper field={field}>
            <div className="w-full space-y-2 overflow-hidden border-0 p-0">
                {field.properties?.choices?.map((choice) => (
                    <div
                        style={{
                            background: selectedItems.includes(choice.value || '')
                                ? theme?.tertiary
                                : '',
                            borderColor: theme?.tertiary
                        }}
                        className="flex cursor-pointer justify-between rounded-xl border p-2 px-4"
                        key={choice.value}
                        onClick={() => handleClick(choice.value || '')}
                    >
                        {choice.value}{' '}
                        {selectedItems.includes(choice.value || '') && <Check />}
                    </div>
                ))}
            </div>
        </QuestionWrapper>
    );
};

const YesNoField = ({ field }: { field: FormField }) => {
    const { addFieldChoiceAnswer } = useFormResponse();
    const theme = useFormTheme();
    return (
        <QuestionWrapper field={field}>
            <RadioGroup
                className={'flex w-full flex-col gap-2'}
                onChange={(value) => addFieldChoiceAnswer(field.id, value)}
            >
                {field &&
                    field.properties?.choices?.map((choice, index) => {
                        return (
                            <RadioGroup.Option
                                value={choice.value}
                                key={index}
                                as={Fragment}
                            >
                                {({ active, checked }) => {
                                    return (
                                        <div
                                            style={{
                                                borderColor: theme?.tertiary,
                                                background: active
                                                    ? theme?.secondary
                                                    : checked
                                                      ? theme?.tertiary
                                                      : ''
                                            }}
                                            className={`flex cursor-pointer justify-between rounded-xl border p-2 px-4`}
                                        >
                                            {choice.value}
                                            {checked && <Check />}
                                        </div>
                                    );
                                }}
                            </RadioGroup.Option>
                        );
                    })}
            </RadioGroup>
        </QuestionWrapper>
    );
};

export default function FormSlide({ index }: { index: number }) {
    const formSlide = useFormSlide(index);
    const { currentSlide, setCurrentSlideToThankyouPage, nextSlide } =
        useFormResponse();
    const { standardForm } = useStandardForm();
    return (
        <div
            className="grid h-full w-full grid-cols-2"
            style={{ background: standardForm.theme?.accent }}
        >
            <ScrollArea className="h-full flex-1 overflow-y-auto">
                <div className="flex h-full flex-col items-center justify-center py-4">
                    <div className="  w-full max-w-[544px] px-10">
                        {formSlide?.properties?.fields?.map((field) => (
                            <div className="mt-20" key={field.index}>
                                <FormFieldComponent field={field} form={standardForm} />
                            </div>
                        ))}
                        <Button
                            style={{ background: standardForm.theme?.secondary }}
                            className="mt-20"
                            onClick={() => {
                                if (currentSlide + 1 === standardForm?.fields?.length) {
                                    setCurrentSlideToThankyouPage();
                                } else {
                                    nextSlide();
                                }
                            }}
                        >
                            Next
                        </Button>
                    </div>
                </div>
            </ScrollArea>
            <div className="relative h-full w-full">
                <Image
                    src={DemoImage}
                    alt="Demo Image"
                    fill
                    style={{
                        objectFit: 'cover'
                    }}
                    priority
                    sizes="(min-w: 0px) 100%"
                />
            </div>
        </div>
    );
}
