'use client';

import { useEffect } from 'react';

import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useGetFormResponseQuery } from '@app/store/redux/formApi';
import { selectWorkspace } from '@app/store/workspaces/slice';
import ThankyouPage from '@app/views/organism/Form/ThankyouPage';
import WelcomePage from '@app/views/organism/Form/WelcomePage';
import FormSlidePreview from '@app/views/organism/FormPreview/FormSlidePreview';
import {extractTextfromJSON} from "@app/utils/richTextEditorExtenstion/getHtmlFromJson";
import {getAnswerForField} from "@app/utils/formBuilderBlockUtils";
import {FieldTypes, StandardFormFieldDto} from "@app/models/dtos/form";

export default function ResponsePage({ searchParams }: { searchParams: { responseId?: string } }) {
    const standardForm = useAppSelector(selectForm);
    const { setFormResponse } = useFormResponse();
    const workspace = useAppSelector(selectWorkspace);
    const { data } = useGetFormResponseQuery(
        {
            workspaceId: workspace.id,
            responseId: searchParams?.responseId
        },
        {
            skip: !(workspace.id && searchParams?.responseId)
        }
    );

    useEffect(() => {
        if (data?.response?.responseId) {
            setFormResponse({
                formId: standardForm.formId,
                answers: data?.response?.answers
            });
        }
    }, [data?.response?.responseId]);

    const IgnoredResponsesFieldType = [FieldTypes.TEXT, null, FieldTypes.IMAGE_CONTENT, FieldTypes.VIDEO_CONTENT];
    function getFormFields() {
        const fields = data?.form.fields?.map((slide:any) => {
            return slide?.properties?.fields?.filter((field: any) => !IgnoredResponsesFieldType.includes(field.type));
        });
        if (fields){
            console.log("asd ",fields.flat())
            return  fields.flat();
        }
        else{
            return []
        }

    }

    return (
        <div className="h-full w-full md:px-28">
            <div className="h-full flex flex-col gap-8 overflow-y-auto p-4 pt-6 ">
                <span>Response: </span>
                {getFormFields().map((field:any) => {
                    return (
                        <div className="flex flex-col gap-1" key={field.id}>
                            <span className="p4-new text-black-500">{extractTextfromJSON(field)}</span>
                            <span className="p2-new text-black-700">{getAnswerForField(data?.response, field) || '- -'}</span>
                        </div>
                    );
                })}
            </div>
            {/*<ScrollArea className="overfloe-y-auto  flex h-full w-full flex-col">*/}
            {/*    <div className="pointer-events-none">*/}
            {/*        <div className="p-4">*/}
            {/*            <div className="border-black-400 min-h-screen w-full overflow-hidden rounded-xl border">*/}
            {/*                <WelcomePage isPreviewMode />*/}
            {/*            </div>*/}
            {/*        </div>*/}
            {/*        {standardForm?.fields?.map((slide, index) => {*/}
            {/*            return (*/}
            {/*                <div className="p-4" key={index}>*/}
            {/*                    <div className="min-w-screen border-black-400 aspect-video h-full w-full overflow-hidden rounded-xl border ">*/}
            {/*                        <FormSlidePreview slide={slide} />*/}
            {/*                    </div>*/}
            {/*                </div>*/}
            {/*            );*/}
            {/*        })}*/}
            {/*        <div className="p-4">*/}
            {/*            <div className="border-black-400 min-h-screen w-full overflow-hidden rounded-xl border ">*/}
            {/*                <ThankyouPage isPreviewMode />*/}
            {/*            </div>*/}
            {/*        </div>*/}
            {/*    </div>*/}
            {/*</ScrollArea>*/}
        </div>
    );
}
