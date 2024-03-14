'use client';

import Image from 'next/image';

import parse from 'html-react-parser';
import { toast } from 'react-toastify';

import DemoImage from '@app/assets/image/rectangle.png';
import { FieldTypes, FormField } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import StandardForm, {
    useFormSlide,
    useStandardForm
} from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import useWorkspace from '@app/store/jotai/workspace';
import { useSubmitResponseMutation } from '@app/store/redux/formApi';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/getHtmlFromJson';
import DropDownField from '@app/views/molecules/ResponderFormFields/DropDownField';
import FileUploadField from '@app/views/molecules/ResponderFormFields/FileUploadField';
import { validateSlide } from '@app/utils/validationUtils';
import InputField from '@app/views/molecules/ResponderFormFields/InputField';
import MultipleChoiceField from '@app/views/molecules/ResponderFormFields/MultipleChoiceField';
import QuestionWrapper from '@app/views/molecules/ResponderFormFields/QuestionQwrapper';
import YesNoField from '@app/views/molecules/ResponderFormFields/YesNoField';

function FormFieldComponent({ field, form }: { field: FormField; form: StandardForm }) {
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
            return <MultipleChoiceField field={field} />;
        case FieldTypes.YES_NO:
            return <YesNoField field={field} />;
        case FieldTypes.FILE_UPLOAD:
            return <FileUploadField field={field} />;
        case FieldTypes.DROP_DOWN:
            return <DropDownField field={field} />;
        case FieldTypes.DATE:
        default:
            return <QuestionWrapper field={field} />;
    }
}

export default function FormSlide({ index }: { index: number }) {
    const formSlide = useFormSlide(index);
    const { currentSlide, setCurrentSlideToThankyouPage, nextSlide } =
        useFormResponse();
    const { standardForm } = useStandardForm();
    const { formResponse, setInvalidFields } = useFormResponse();
    const { workspace } = useWorkspace();
    const [submitResponse, { data }] = useSubmitResponseMutation();

    const submitFormResponse = async () => {
        const formData = new FormData();

        const postBody = {
            form_id: standardForm?.formId,
            answers: formResponse.answers
        };

        formData.append('response', JSON.stringify(postBody));

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
                            onClick={onNext}
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
