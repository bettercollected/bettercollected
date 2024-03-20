'use client';

import { useRef, useState } from 'react';

import Image from 'next/image';

import { AnimatePresence, motion } from 'framer-motion';
import parse from 'html-react-parser';
import { toast } from 'react-toastify';

import DemoImage from '@app/assets/image/rectangle.png';
import { FieldTypes, FormField } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { useFormSlide, useStandardForm } from '@app/store/jotai/fetchedForm';
import useFormAtom from '@app/store/jotai/formFile';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import useWorkspace from '@app/store/jotai/workspace';
import { useSubmitResponseMutation } from '@app/store/redux/formApi';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/getHtmlFromJson';
import { validateSlide } from '@app/utils/validationUtils';
import DateField from '@app/views/molecules/ResponderFormFields/DateField';
import DropDownField from '@app/views/molecules/ResponderFormFields/DropDownField';
import FileUploadField from '@app/views/molecules/ResponderFormFields/FileUploadField';
import InputField from '@app/views/molecules/ResponderFormFields/InputField';
import MultipleChoiceField from '@app/views/molecules/ResponderFormFields/MultipleChoiceField';
import MultipleChoiceWithMultipleSelection from '@app/views/molecules/ResponderFormFields/MultipleChoiceWirhMultipleSelections';
import PhoneNumberField from '@app/views/molecules/ResponderFormFields/PhoneNumberField';
import QuestionWrapper from '@app/views/molecules/ResponderFormFields/QuestionQwrapper';
import RatingField from '@app/views/molecules/ResponderFormFields/RatingField';
import YesNoField from '@app/views/molecules/ResponderFormFields/YesNoField';

function FormFieldComponent({
    field,
    slideIndex
}: {
    field: FormField;
    slideIndex: number;
}) {
    switch (field.type) {
        case FieldTypes.TEXT:
            return (
                <div className="h1-new w-full text-left text-[32px] font-bold">
                    {parse(getHtmlFromJson(field?.title) ?? 'No Fields')}
                </div>
            );
        case FieldTypes.NUMBER:
        case FieldTypes.EMAIL:
        case FieldTypes.SHORT_TEXT:
        case FieldTypes.LINK:
            return <InputField field={field} />;
        case FieldTypes.MULTIPLE_CHOICE:
            if (field?.properties?.allowMultipleSelection) {
                return (
                    <MultipleChoiceWithMultipleSelection
                        field={field}
                        slideIndex={slideIndex}
                    />
                );
            }
            return <MultipleChoiceField field={field} slideIndex={slideIndex} />;
        case FieldTypes.YES_NO:
            return <YesNoField field={field} />;
        case FieldTypes.FILE_UPLOAD:
            return <FileUploadField field={field} />;
        case FieldTypes.DROP_DOWN:
            return <DropDownField field={field} slideIndex={slideIndex} />;
        case FieldTypes.DATE:
        case FieldTypes.PHONE_NUMBER:
            return <PhoneNumberField field={field} />;
        case FieldTypes.RATING:
            return <RatingField field={field} />;
        case FieldTypes.DATE:
            return <DateField field={field} />;
        default:
            return <QuestionWrapper field={field} />;
    }
}

export default function FormSlide({ index }: { index: number }) {
    const formSlide = useFormSlide(index);
    const {
        currentSlide,
        setCurrentSlideToThankyouPage,
        nextSlide,
        prevActiveField,
        currentField,
        setCurrentField
    } = useFormResponse();
    const { standardForm } = useStandardForm();
    const { formResponse, setInvalidFields } = useFormResponse();
    const { workspace } = useWorkspace();
    const [submitResponse] = useSubmitResponseMutation();
    const { files } = useFormAtom();

    const handleFieldChange = (newCurrentField: number) => {
        setCurrentField(newCurrentField);
    };

    const submitFormResponse = async () => {
        const formData = new FormData();

        const postBody = {
            form_id: standardForm?.formId,
            answers: formResponse.answers ?? {}
        };

        formData.append('response', JSON.stringify(postBody));
        files.forEach((fileObj) => {
            formData.append('files', fileObj.file, fileObj.fileName);
            formData.append('file_field_ids', fileObj.fieldId);
            formData.append('file_ids', fileObj.fileId);
        });

        const response: any = await submitResponse({
            workspaceId: workspace.id,
            formId: standardForm?.formId,
            body: formData
        });
        if (!response.data) {
            throw new Error(response?.error);
        }
    };

    const onNext = () => {
        const invalidations = validateSlide(formSlide!, formResponse.answers || {});
        setInvalidFields(invalidations);
        if (Object.values(invalidations).length === 0) {
            if (currentSlide + 1 === standardForm?.fields?.length) {
                submitFormResponse()
                    .then(() => {
                        setCurrentSlideToThankyouPage();
                    })
                    .catch((e) => {
                        toast('Error Submitting Response');
                    });
            } else {
                nextSlide();
            }
        }
    };

    const transitionClass = 'transition-opacity duration-300 ease-in-out';

    return (
        <div
            className="grid h-full w-full grid-cols-2"
            style={{ background: standardForm.theme?.accent }}
        >
            <ScrollArea asChild className="h-full flex-1 overflow-y-auto">
                <AnimatePresence mode="wait">
                    <div className=" flex h-full flex-col items-center justify-center py-4">
                        <div className="  w-full max-w-[800px] px-10">
                            {formSlide?.properties?.fields?.map((field, index) => (
                                <>
                                    {currentField - 1 === index && (
                                        <motion.div
                                            initial={{
                                                y:
                                                    prevActiveField < currentField
                                                        ? '100%'
                                                        : '-100%'
                                            }}
                                            animate={{ y: 0 }}
                                            className={`relative h-[200px] overflow-y-hidden`}
                                            onClick={() => {
                                                handleFieldChange(currentField - 1);
                                            }}
                                        >
                                            <div
                                                className="absolute bottom-0 left-0 right-0 top-0 z-[10]"
                                                style={{
                                                    background: `linear-gradient(360deg, transparent 0%, ${standardForm.theme?.accent} 100%)`
                                                }}
                                            />
                                            <div className="absolute bottom-0 w-full">
                                                <FormFieldComponent
                                                    field={
                                                        formSlide!.properties!.fields![
                                                            currentField - 1
                                                        ]
                                                    }
                                                    slideIndex={formSlide!.index}
                                                />
                                            </div>
                                        </motion.div>
                                    )}
                                    {currentField === index && (
                                        <motion.div
                                            initial={{
                                                y:
                                                    prevActiveField < currentField
                                                        ? '100%'
                                                        : '-100%'
                                            }}
                                            animate={{ y: 0 }}
                                            className={`mt-20 ${transitionClass}`}
                                        >
                                            <FormFieldComponent
                                                field={
                                                    formSlide!.properties!.fields![
                                                        currentField
                                                    ]
                                                }
                                                slideIndex={formSlide!.index}
                                            />
                                        </motion.div>
                                    )}

                                    {currentField + 1 === index && (
                                        <motion.div
                                            id={
                                                formSlide!.properties!.fields![
                                                    currentField - 1
                                                ]?.id
                                            }
                                            initial={{
                                                y:
                                                    prevActiveField < currentField
                                                        ? '100%'
                                                        : '-100%'
                                            }}
                                            animate={{ y: 0 }}
                                            className={`relative mt-20 ${transitionClass}`}
                                            onClick={() => {
                                                handleFieldChange(currentField + 1);
                                            }}
                                        >
                                            <div className="relative max-h-[200px] overflow-hidden">
                                                <div
                                                    className="absolute bottom-0 left-0 right-0 top-0 z-[10]"
                                                    style={{
                                                        background: `linear-gradient(180deg, transparent 0%, ${standardForm.theme?.accent} 100%)`
                                                    }}
                                                />
                                                <FormFieldComponent
                                                    field={
                                                        formSlide!.properties!.fields![
                                                            currentField + 1
                                                        ]
                                                    }
                                                    slideIndex={formSlide!.index}
                                                />
                                            </div>
                                        </motion.div>
                                    )}
                                </>
                            ))}

                            {currentField + 1 ===
                                formSlide?.properties?.fields?.length && (
                                <Button
                                    style={{
                                        background: standardForm.theme?.secondary
                                    }}
                                    className="mt-20 rounded px-8 py-3"
                                    onClick={onNext}
                                    size="medium"
                                >
                                    Next
                                </Button>
                            )}
                        </div>
                    </div>
                </AnimatePresence>
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
