import parse from 'html-react-parser';

import { FieldTypes, FormField } from '@app/models/dtos/form';
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
