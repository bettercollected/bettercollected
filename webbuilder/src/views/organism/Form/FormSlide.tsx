'use client';

import { useCallback, useEffect } from 'react';

import { AnimatePresence, motion } from 'framer-motion';
import parse from 'html-react-parser';
import { ChevronLeft } from 'lucide-react';
import { Controller } from 'react-scrollmagic';
import { toast } from 'react-toastify';
import { useDebounceCallback } from 'usehooks-ts';

import { FieldTypes, FormField } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { cn } from '@app/shadcn/util/lib';
import { useAuthAtom } from '@app/store/jotai/auth';
import { useFormSlide, useStandardForm } from '@app/store/jotai/fetchedForm';
import useFormAtom from '@app/store/jotai/formFile';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import useWorkspace from '@app/store/jotai/workspace';
import { useSubmitResponseMutation } from '@app/store/redux/formApi';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/getHtmlFromJson';
import { validateSlide } from '@app/utils/validationUtils';
import FullScreenLoader from '@app/views/atoms/Loaders/FullScreenLoader';
import DateField from '@app/views/molecules/ResponderFormFields/DateField';
import DropDownField from '@app/views/molecules/ResponderFormFields/DropDownField';
import FileUploadField from '@app/views/molecules/ResponderFormFields/FileUploadField';
import InputField from '@app/views/molecules/ResponderFormFields/InputField';
import LinearRatingField from '@app/views/molecules/ResponderFormFields/LinearRating';
import MultipleChoiceField from '@app/views/molecules/ResponderFormFields/MultipleChoiceField';
import MultipleChoiceWithMultipleSelection from '@app/views/molecules/ResponderFormFields/MultipleChoiceWirhMultipleSelections';
import PhoneNumberField from '@app/views/molecules/ResponderFormFields/PhoneNumberField';
import QuestionWrapper from '@app/views/molecules/ResponderFormFields/QuestionQwrapper';
import RatingField from '@app/views/molecules/ResponderFormFields/RatingField';
import YesNoField from '@app/views/molecules/ResponderFormFields/YesNoField';

import SlideLayoutWrapper from '../Layout/SlideLayoutWrapper';

export function FormFieldComponent({
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
                    {parse(getHtmlFromJson(field?.title) ?? 'Add Text')}
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
        case FieldTypes.PHONE_NUMBER:
            return <PhoneNumberField field={field} />;
        case FieldTypes.RATING:
            return <RatingField field={field} />;
        case FieldTypes.DATE:
            return <DateField field={field} />;
        case FieldTypes.LINEAR_RATING:
            return <LinearRatingField field={field} />;
        default:
            return <QuestionWrapper field={field} />;
    }
}

export default function FormSlide({
    index,
    isPreviewMode = false
}: {
    index: number;
    isPreviewMode: boolean;
}) {
    const formSlide = useFormSlide(index);

    const {
        currentSlide,
        setCurrentSlideToThankyouPage,
        nextSlide,
        previousSlide,
        currentField,
        setCurrentField
    } = useResponderState();
    const { standardForm } = useStandardForm();
    const { formResponse, setInvalidFields, setFormResponse } = useFormResponse();
    const { workspace } = useWorkspace();
    const [submitResponse, { isLoading }] = useSubmitResponseMutation();
    const { files } = useFormAtom();
    const { authState } = useAuthAtom();

    const handleFieldChange = (newCurrentField: number) => {
        setCurrentField(newCurrentField);
    };

    const onScroll = useCallback(
        (direction: number) => {
            if (direction === -1 && currentField === 0) {
                return;
            }
            if (
                direction === 1 &&
                currentField === (formSlide?.properties?.fields?.length || 0) - 1
            ) {
                return;
            }
            // setCurrentField(currentField + direction);

            const fieldId =
                formSlide?.properties?.fields &&
                formSlide?.properties?.fields[currentField + direction].id;
            fieldId && handleClickField(currentField + direction, fieldId);
        },
        [currentField]
    );

    const onScrollDebounced = useDebounceCallback(onScroll, 200);

    const submitFormResponse = async () => {
        const formData = new FormData();

        const postBody = {
            form_id: standardForm?.formId,
            answers: formResponse.answers ?? {},
            anonymize: formResponse.anonymize ?? false
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
        if (Object.keys(invalidations).length === 0) {
            if (currentSlide + 1 === standardForm?.fields?.length) {
                if (isPreviewMode) setCurrentSlideToThankyouPage();
                else
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
        } else {
            const firstInvalidField = formSlide?.properties?.fields?.find(
                (field) => Object.keys(invalidations)[0] === field.id
            );
            setCurrentField(firstInvalidField!.index);
        }
    };

    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            const ARROW_DOWN = 'ArrowDown';
            const ARROW_UP = 'ArrowUp';
            const ENTER = 'Enter';
            const TAB = 'Tab';

            switch (event.key) {
                case ENTER:
                case TAB:
                case ARROW_DOWN:
                    event.preventDefault();
                    onScrollDebounced(1);
                    break;
                case ARROW_UP:
                    event.preventDefault();
                    onScrollDebounced(-1);
                    break;
                default:
                    break;
            }
        };

        window.addEventListener('keydown', handleKeyDown);

        return () => {
            window.removeEventListener('keydown', handleKeyDown);
        };
    }, [onScrollDebounced, currentField]);

    const handleClickField = (index: number, fieldId: string) => {
        setCurrentField(index);

        document.getElementById(`input-field-${fieldId}`)?.focus();
    };

    if (!formSlide) return <FullScreenLoader />;

    // const checkPreviousFieldIsTextField = (index: number) => {
    //     if (index === 0) return false;
    //     return formSlide.properties?.fields![index - 1].type === FieldTypes.TEXT;
    // };

    // const findTextField = (field: FormField) => {
    //     if (field.index !== 0) {
    //         const previousField = formSlide?.properties?.fields![field.index - 1];
    //         if (previousField?.type === FieldTypes.TEXT) return;
    //     }

    //     return getTextField(field);
    // };

    // function getTextField(field: FormField): any {
    //     const nextField = formSlide?.properties?.fields![field.index + 1];
    //     return (
    //         <>
    //             <div className="h1-new w-full text-left text-[32px] font-bold">
    //                 {parse(getHtmlFromJson(field?.title) ?? 'Add Text')}
    //             </div>
    //             {nextField?.type === FieldTypes.TEXT && getTextField(nextField)}
    //             <FormFieldComponent
    //                 field={formSlide!.properties!.fields![field.index + 1]}
    //                 slideIndex={formSlide!.index}
    //             />
    //         </>
    //     );
    // }

    return (
        <Controller>
            <SlideLayoutWrapper theme={standardForm.theme} slide={formSlide} disabled>
                {currentSlide > 0 && (
                    <div
                        className="absolute left-5 top-8 z-[100] flex cursor-pointer gap-2 lg:left-20"
                        onClick={() => {
                            previousSlide();
                        }}
                    >
                        <ChevronLeft className="text-black-700" />{' '}
                        <span className="text-black-700">Back</span>
                    </div>
                )}
                <div
                    className={cn(
                        'flex h-full flex-1 flex-col justify-center ',
                        formSlide?.properties?.layout ===
                            FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN
                            ? 'items-start '
                            : 'items-center'
                    )}
                    onWheel={(event) => {
                        onScrollDebounced(event?.deltaY > 0 ? 1 : -1);
                    }}
                >
                    <AnimatePresence mode="wait">
                        <div
                            className={cn(
                                'grid h-full w-full max-w-[800px] grid-cols-1 content-center items-center justify-center overflow-hidden px-4 py-20 lg:px-20'
                            )}
                        >
                            {formSlide?.properties?.fields?.map((field, index) => (
                                <motion.div
                                    onClick={() => handleClickField(index, field.id)}
                                    key={field.id}
                                    initial={{ opacity: 0, y: 0 }}
                                    animate={{
                                        opacity: currentField === index ? 1 : 0.4,
                                        y: currentField === index ? 0 : -10
                                    }}
                                    transition={{
                                        type: 'tween',
                                        stiffness: 260,
                                        ease: 'easeInOut',
                                        damping: 20,
                                        duration: 0.5
                                    }}
                                    className={cn('relative my-3 cursor-pointer')}
                                >
                                    <div
                                        id={field.id}
                                        className={cn(
                                            'my-3 transition-all duration-500 ease-linear',
                                            currentField === index
                                                ? 'min-h-fit opacity-100'
                                                : currentField - 1 === index
                                                  ? ' my-0 h-[140px] overflow-hidden opacity-40'
                                                  : currentField + 1 === index
                                                    ? 'my-0 h-[140px] overflow-hidden opacity-40'
                                                    : ' my-0 h-0 overflow-hidden opacity-0 '
                                        )}
                                    >
                                        <FormFieldComponent
                                            field={
                                                formSlide!.properties!.fields![index]
                                            }
                                            slideIndex={formSlide!.index}
                                        />
                                    </div>
                                </motion.div>
                            ))}

                            {(!formSlide?.properties?.fields?.length ||
                                currentField + 1 ===
                                    formSlide?.properties?.fields?.length) && (
                                <motion.div
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    transition={{
                                        type: 'tween',
                                        stiffness: 260,
                                        ease: 'easeInOut',
                                        damping: 20,
                                        duration: 0.5
                                    }}
                                    className="flex flex-col"
                                >
                                    {(standardForm?.fields?.length || 0) - 1 ===
                                        currentSlide && (
                                        <div className="mt-20 flex flex-col">
                                            {authState.id &&
                                                !standardForm.settings
                                                    ?.requireVerifiedIdentity && (
                                                    <div className="flex flex-row gap-2 text-sm ">
                                                        <FieldInput
                                                            checked={
                                                                formResponse.anonymize
                                                            }
                                                            onChange={(e) =>
                                                                setFormResponse({
                                                                    ...formResponse,
                                                                    anonymize:
                                                                        e.target.checked
                                                                })
                                                            }
                                                            type="checkbox"
                                                            className="h-4 w-4 border focus:border-0 focus:outline-none"
                                                        />
                                                        Hide your email from Form
                                                        Collector
                                                    </div>
                                                )}
                                            {authState.id && (
                                                <div
                                                    className={`p2-new mt-2 italic text-black-600 `}
                                                >
                                                    {authState?.id &&
                                                    !formResponse.anonymize
                                                        ? `You are submitting this form as ${authState?.email}`
                                                        : 'Your identity is hidden from form creator.'}{' '}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                    <Button
                                        style={{
                                            background: standardForm.theme?.secondary
                                        }}
                                        isLoading={isLoading}
                                        className="mt-4 rounded px-8 py-3"
                                        onClick={onNext}
                                        size="medium"
                                    >
                                        {(standardForm?.fields?.length || 0) - 1 ===
                                        currentSlide
                                            ? 'Submit'
                                            : 'Next'}
                                    </Button>
                                </motion.div>
                            )}
                        </div>
                    </AnimatePresence>
                </div>
            </SlideLayoutWrapper>
        </Controller>
    );
}
