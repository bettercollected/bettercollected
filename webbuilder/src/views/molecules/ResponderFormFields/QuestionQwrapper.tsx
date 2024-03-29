import parse from 'html-react-parser';

import { FieldTypes, FormField } from '@app/models/dtos/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/getHtmlFromJson';
import RequiredIcon from '@app/views/atoms/Icons/Required';

import { getPlaceholderValueForTitle } from '../RichTextEditor';

export default function QuestionWrapper({
    field,
    children
}: {
    field: FormField;
    children?: React.ReactNode;
}) {
    const { formResponse } = useFormResponse();

    const { invalidFields } = formResponse;

    return (
        <div className="relative flex flex-col">
            {field?.validations?.required && (
                <div className="top- 2 absolute -right-10">
                    <RequiredIcon className="text-black-900" />
                </div>
            )}
            <div className="mb-4">
                <div className="font-semibold">
                    {parse(
                        getHtmlFromJson(field?.title) ??
                            getPlaceholderValueForTitle(field?.type || FieldTypes.TEXT)
                    )}
                </div>
                {field?.description && (
                    <div className="mt-1 text-black-700">{field?.description}</div>
                )}
            </div>
            {children}
            {invalidFields &&
                invalidFields[field.id] &&
                invalidFields[field.id].length && (
                    <div className="mt-2 text-red-500">*Field Required</div>
                )}
        </div>
    );
}
