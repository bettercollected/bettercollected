'use client';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useGetFormResponseQuery } from '@app/store/redux/formApi';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { getAnswerForField } from '@app/utils/formBuilderBlockUtils';
import { getFieldsFromV2Form } from '@app/utils/formUtils';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/getHtmlFromJson';
import { useEffect } from 'react';

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

    function getFormFields() {
        if (data?.form) {
            return getFieldsFromV2Form(data.form);
        }
        return [];
    }

    return (
        <div className="h-full w-full md:px-28">
            <div className="flex h-full flex-col gap-8 overflow-y-auto p-4 pt-6 ">
                <span>Response: </span>
                {getFormFields().map((field: any) => {
                    return (
                        <div className="flex flex-col gap-1" key={field.id}>
                            <span className="p4-new text-black-500">{extractTextfromJSON(field)}</span>
                            <span className="p2-new text-black-700">{getAnswerForField(data?.response, field) || '- -'}</span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
