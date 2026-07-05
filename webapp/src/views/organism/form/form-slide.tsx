'use client';

import { useToast } from '@app/shadcn/components/ui/use-toast';
import { Controller } from 'react-scrollmagic';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import useFormAtom from '@app/store/jotai/form-file';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { useSubmitResponseMutation } from '@app/store/redux/form-api';
import { validateSlide } from '@app/utils/vvalidation-utils';
import FullScreenLoader from '@app/views/atoms/full-screen-loader';
import DateField from '@app/views/molecules/responder-form-fields/date-field';
import DropDownField from '@app/views/molecules/responder-form-fields/drop-down-field';
import FileUploadField from '@app/views/molecules/responder-form-fields/file-upload-field';
import InputField from '@app/views/molecules/responder-form-fields/input-field';
import LinearRatingField from '@app/views/molecules/responder-form-fields/linear-rating';
import MultipleChoiceField from '@app/views/molecules/responder-form-fields/multiple-choice-field';
import MultipleChoiceWithMultipleSelection from '@app/views/molecules/responder-form-fields/multiple-choice-with-multiple-selections';
import PhoneNumberField from '@app/views/molecules/responder-form-fields/phone-number-field';
import QuestionWrapper from '@app/views/molecules/responder-form-fields/question-wrapper';
import RatingField from '@app/views/molecules/responder-form-fields/rating-field';
import YesNoField from '@app/views/molecules/responder-form-fields/yes-no-field';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { scrollToDivById } from '@app/utils/scroll-utils';
import BackButton from '@app/views/molecules/form-builder/back-button';
import TextAreaField from '@app/views/molecules/responder-form-fields/text-area-field';
import ImageField from '../form-builder/fields/image-field';
import MatrixField from '../form-builder/fields/matrix';
import VideoField from '../form-builder/fields/video-field';
import SlideLayoutWrapper from '../layout/slide-layout-wrapper';

export function FormFieldComponent({ field, slideIndex }: { field: StandardFormFieldDto; slideIndex: number }) {
    switch (field.type) {
        case FieldTypes.TEXT:
            return <QuestionWrapper field={field} />;
        case FieldTypes.EMAIL:
        case FieldTypes.NUMBER:
        case FieldTypes.LINK:
            return <InputField field={field} />;
        case FieldTypes.SHORT_TEXT:
        case FieldTypes.LONG_TEXT:
            return <TextAreaField field={field} />;
        case FieldTypes.MULTIPLE_CHOICE:
            if (field?.properties?.allowMultipleSelection) {
                return <MultipleChoiceWithMultipleSelection field={field} slideIndex={slideIndex} />;
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
        case FieldTypes.IMAGE_CONTENT:
            return <ImageField field={field} />;
        case FieldTypes.VIDEO_CONTENT:
            return <VideoField field={field} />;
        case FieldTypes.MATRIX:
            return (
                <QuestionWrapper field={field}>
                    <MatrixField field={field} />
                </QuestionWrapper>
            );
        default:
            return <QuestionWrapper field={field} />;
    }
}

export default function FormSlide({ index, formSlideData, isPreviewMode = false, showDesktopLayout }: { index: number; isPreviewMode: boolean; formSlideData?: any; showDesktopLayout?: boolean }) {
    const { toast } = useToast();
    const standardForm = useAppSelector(selectForm);
    const formSlideFromState = standardForm.fields[index];
    const formSlide = formSlideData ? formSlideData : formSlideFromState;

    const { currentSlide, setCurrentSlideToThankyouPage, nextSlide, previousSlide, setResponderState, responderState, setCurrentSlideToWelcomePage } = useResponderState();

    const { formResponse, setInvalidFields, setFormResponse } = useFormResponse();
    const workspace = useAppSelector(selectWorkspace);
    const [submitResponse, { isLoading }] = useSubmitResponseMutation();
    const { files } = useFormAtom();
    const authState = useAppSelector(selectAuth);

    const submitFormResponse = async () => {
        const formData = new FormData();

        const postBody = {
            form_id: standardForm?.formId,
            answers: formResponse.answers ?? {},
            anonymize: formResponse.anonymize ?? false,
            form_version: standardForm?.version || 1
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
        return response.data;
    };

    const onNext = () => {
        const invalidations = validateSlide(formSlide!, formResponse.answers || {});
        setInvalidFields(invalidations);
        if (Object.keys(invalidations).length === 0) {
            if (currentSlide + 1 === standardForm?.fields?.length) {
                if (isPreviewMode) setCurrentSlideToThankyouPage();
                else
                    submitFormResponse()
                        .then((responderId) => {
                            setResponderState({
                                ...responderState,
                                currentSlide: -2,
                                responderId
                            });
                        })
                        .catch((e) => {
                            debugger;
                            toast({ description: 'Error Submitting Response', variant: 'destructive' });
                        });
            } else {
                nextSlide();
            }
        } else {
            const firstInvalidField = formSlide?.properties?.fields?.find((field: StandardFormFieldDto) => Object.keys(invalidations)[0] === field.id);
            if (firstInvalidField) {
                scrollToDivById(firstInvalidField.id);
            }
        }
    };

    if (!formSlide) return <FullScreenLoader />;

    return (
        <Controller>
            <SlideLayoutWrapper showDesktopLayout={showDesktopLayout} scrollDivId={'questions-container'} theme={standardForm.theme} slide={formSlide} disabled>
                <div className="absolute left-0 right-0 top-5 z-10 mx-auto w-full ">
                    <div className="px-5 md:px-8 xl:px-10 2xl:px-20">
                        <div className={`w-full max-w-[800px] px-4 ${formSlide?.properties?.layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN ? '' : 'mx-auto'}`}>
                            <BackButton
                                handleClick={() => {
                                    currentSlide > 0 ? previousSlide() : setCurrentSlideToWelcomePage();
                                }}
                                className=" w-fit !bg-inherit"
                                style={{
                                    background: standardForm?.theme?.accent
                                }}
                            />
                        </div>
                    </div>
                </div>
                <div className={cn('flex h-full flex-1 flex-col justify-center ', formSlide?.properties?.layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN ? 'items-start ' : 'items-center')}>
                    <div className={cn('relative flex h-full w-full max-w-[800px] flex-col gap-[48px] overflow-hidden px-4 lg:gap-[120px] py-[60px]', isPreviewMode ? '' : 'lg:px-10')}>
                        {formSlide?.properties?.fields?.map((field: StandardFormFieldDto, index: number) => (
                            <FormFieldComponent key={field.id} field={formSlide!.properties!.fields![index]} slideIndex={formSlide!.index} />
                        ))}
                        <div>
                            {(standardForm?.fields?.length || 0) - 1 === currentSlide && currentSlide === index && (
                                <div className="flex flex-col lg:mb-4 ">
                                    {authState.id && !standardForm.settings?.requireVerifiedIdentity && (
                                        <div className="flex flex-row gap-2 ">
                                            <FieldInput
                                                checked={!formResponse.anonymize}
                                                onChange={(e: any) => {
                                                    setFormResponse({
                                                        ...formResponse,
                                                        anonymize: !e.target.checked
                                                    });
                                                }}
                                                type="checkbox"
                                                className="h-4 w-4 border focus:border-0 focus:outline-none"
                                            />
                                            <div className="flex flex-col ">
                                                <span className="text-black-800 text-xs font-medium">Show your identity(email) to form collector</span>
                                                <span className={`p4-new text-black-600 `}>{authState?.email} </span>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                            <Button
                                style={{
                                    background: standardForm.theme?.secondary,
                                    color: 'white'
                                }}
                                isLoading={isLoading}
                                className=" rounded px-8 py-3 mt-4"
                                onClick={onNext}
                                size="medium"
                            >
                                {(standardForm?.fields?.length || 0) - 1 === currentSlide && currentSlide === index ? 'Submit' : 'Next'}
                            </Button>
                        </div>
                    </div>
                    {/* <div style={{ background: standardForm.theme?.accent }} className="border-black-200 absolute bottom-0 left-0 flex w-full flex-col gap-4 border-t bg-opacity-100 p-4 lg:hidden">
                        {(standardForm?.fields?.length || 0) - 1 === currentSlide && currentSlide === index && (
                            <div className="flex flex-col px-5">
                                {authState.id && !standardForm.settings?.requireVerifiedIdentity && (
                                    <div className="flex flex-row gap-2 ">
                                        <FieldInput
                                            checked={!formResponse.anonymize}
                                            onChange={(e: any) => {
                                                setFormResponse({
                                                    ...formResponse,
                                                    anonymize: !e.target.checked
                                                });
                                            }}
                                            type="checkbox"
                                            className="h-4 w-4 border focus:border-0 focus:outline-none"
                                        />
                                        <div className="flex flex-col ">
                                            <span className="text-black-800 text-xs font-medium">Show your identity(email) to form collector</span>
                                            <span className={`p4-new text-black-600 `}>{authState?.email} </span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                        <div className="flex w-full items-center gap-4">
                            <BackButton
                                handleClick={() => {
                                    currentSlide > 0 ? previousSlide() : setCurrentSlideToWelcomePage();
                                }}
                                className="w-fit !bg-inherit"
                                style={{
                                    background: standardForm?.theme?.accent
                                }}
                            />
                            <Button
                                style={{
                                    background: standardForm.theme?.secondary,
                                    color: 'white'
                                }}
                                isLoading={isLoading}
                                className=" w-full rounded"
                                onClick={onNext}
                                size="medium"
                            >
                                {(standardForm?.fields?.length || 0) - 1 === currentSlide && currentSlide === index ? 'Submit' : 'Next'}
                            </Button>
                        </div>
                    </div> */}
                </div>
            </SlideLayoutWrapper>
        </Controller>
    );
}
