import environments from '@app/configs/environments';
import { StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldTypes } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { extractTextfromJSON } from './richTextEditorExtenstion/getHtmlFromJson';

export default function getFormShareURL(form: StandardFormDto, workspace: WorkspaceDto, defaultLink: boolean = false) {
    const slug = form?.settings?.customUrl || form?.importedFormId;
    const scheme = environments.HTTP_SCHEME;
    let domain = '';

    if (workspace?.isPro && workspace?.customDomain && !defaultLink) {
        domain = workspace.customDomain;
    } else {
        domain = form?.builderVersion === 'v2' ? environments.FORM_DOMAIN : environments.CLIENT_DOMAIN;
    }

    const url = workspace?.isPro && workspace?.customDomain && !defaultLink ? `/forms/${slug}` : `/${workspace.workspaceName}/forms/${slug}`;

    return `${scheme}${domain}${url}`;
}

export function getPlaceholderValueForField(fieldType?: FieldTypes) {
    switch (fieldType) {
        case FieldTypes.EMAIL:
            return 'name@gmail.com';
        case FieldTypes.NUMBER:
            return '123';
        case FieldTypes.SHORT_TEXT:
            return 'Answer';
        case FieldTypes.LINK:
            return 'https://';
        case FieldTypes.PHONE_NUMBER:
            return '0123456789';
        default:
            return 'No Field Selected';
    }
}

const IgnoredResponsesFieldType = [FieldTypes.TEXT, null, FieldTypes.IMAGE_CONTENT, FieldTypes.VIDEO_CONTENT];

export const getFieldsFromV2Form = (form: StandardFormDto) => {
    const fields = form.fields.map((slide) => {
        const filteredFields = slide?.properties?.fields?.filter((field: StandardFormFieldDto) => !IgnoredResponsesFieldType.includes(field.type));
        const filteredFieldsWithMatrix = filteredFields?.map((field: StandardFormFieldDto) => {
            if (field?.type !== FieldTypes.MATRIX) {
                return field;
            }
            const matrixRows = field?.properties?.fields?.map((row: StandardFormFieldDto) => {
                return {
                    ...row,
                    title: `${extractTextfromJSON(field)}[${row.title}]`
                };
            });
            return matrixRows;
        });
        return filteredFieldsWithMatrix;
    });
    return fields.flat(2);
};
