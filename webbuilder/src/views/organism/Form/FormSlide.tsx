'use client';

import React from 'react';

import Image from 'next/image';

import parse from 'html-react-parser';

import DemoImage from '@app/assets/image/rectangle.png';
import { FieldTypes, FormField } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { FieldInput } from '@app/shadcn/components/ui/input';
import {
    useFormSlide,
    useFormTheme,
    useStandardForm
} from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/getHtmlFromJson';
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

function FormFieldComponent({ field }: { field: FormField }) {
    const theme = useFormTheme();
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
                    <FieldInput $slide={field} />
                </QuestionWrapper>
            );
        case FieldTypes.SHORT_TEXT:
            return (
                <QuestionWrapper field={field}>
                    <FieldInput
                        type="text"
                        placeholder={field?.properties?.placeholder}
                        className="mt-4"
                        $formTheme={theme}
                    />
                </QuestionWrapper>
            );
        case FieldTypes.MULTIPLE_CHOICE:
            return (
                <QuestionWrapper field={field}>
                    <div className="mt-4 flex flex-col gap-2">
                        {field?.properties?.choices?.map((choice) => (
                            <div
                                key={choice.id}
                                style={{
                                    color: theme?.secondary,
                                    border: `1px solid ${theme?.tertiary}`
                                }}
                                className="cursor-pointer rounded-lg px-4 py-2"
                            >
                                {choice.value}
                            </div>
                        ))}
                    </div>
                </QuestionWrapper>
            );

        default:
            return <QuestionWrapper field={field} />;
    }
}

export default function FormSlide({ index }: { index: number }) {
    const formSlide = useFormSlide(index);
    const { currentSlide, setCurrentSlideToThankyouPage, nextSlide } =
        useFormResponse();
    const { standardForm } = useStandardForm();
    return (
        <div className="grid h-full w-full grid-cols-2">
            <div className="flex h-full flex-col items-center justify-center">
                <div className="  w-full max-w-[544px] px-10">
                    {formSlide?.properties?.fields?.map((field) => (
                        <div className="mt-20" key={field.index}>
                            <FormFieldComponent field={field} />
                        </div>
                    ))}
                    <Button
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
