'use client';

import Image from 'next/image';

import parse from 'html-react-parser';

import DemoImage from '@app/assets/image/rectangle.png';
import { FieldTypes, FormField } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import StandardForm, {
    useFormSlide,
    useStandardForm
} from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/getHtmlFromJson';
import EmailField from '@app/views/molecules/ResponderFormFields/EmailField';
import MultipleChoiceField from '@app/views/molecules/ResponderFormFields/MultipleChoiceField';
import QuestionWrapper from '@app/views/molecules/ResponderFormFields/QuestionQwrapper';
import ShortTextField from '@app/views/molecules/ResponderFormFields/ShortTextField';
import YesNoField from '@app/views/molecules/ResponderFormFields/YesNoField';

function FormFieldComponent({ field, form }: { field: FormField; form: StandardForm }) {
    const { formResponse } = useFormResponse();
    console.log('sda', formResponse);
    switch (field.type) {
        case FieldTypes.TEXT:
            return (
                <div className="h1-new w-full text-left text-[32px] font-bold">
                    {parse(getHtmlFromJson(field?.title) ?? 'No Fields')}
                </div>
            );
        case FieldTypes.EMAIL:
            return <EmailField field={field} />;
        case FieldTypes.SHORT_TEXT:
            return <ShortTextField field={field} />;
        case FieldTypes.MULTIPLE_CHOICE:
            return <MultipleChoiceField field={field} />;
        case FieldTypes.YES_NO:
            return <YesNoField field={field} />;

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
