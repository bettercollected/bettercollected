import environments from '@app/configs/environments';
import { StandardFormDto } from '@app/models/dtos/form';
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
