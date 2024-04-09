import environments from '@app/configs/environments';
import { StandardFormDto } from '@app/models/dtos/form';
import { FieldTypes } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';


export default function getFormShareURL(form: StandardFormDto, workspace: WorkspaceDto, defaultLink: boolean = false) {
    const slug = form?.settings?.customUrl || form?.formId;
    const scheme = environments.HTTP_SCHEME;
    let domain = '';

    if (workspace?.isPro && workspace?.customDomain && !defaultLink) {
        domain = workspace.customDomain;
    } else {
        domain = form?.builderVersion === 'v2' ? environments.V2_FORM_DOMAIN : environments.CLIENT_DOMAIN;
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