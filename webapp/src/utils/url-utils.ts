import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';

export function isValidRelativeURL(url: string): boolean {
    // Define a regular expression to match valid relative URLs
    const relativeURLPattern = /^\/|^(?!(?:[a-zA-Z]+:|\/\/))[\w\d\-._~:/?#\[\]@!$&'()*+,;=]+$/;

    // Check if the URL matches the pattern
    return relativeURLPattern.test(url) && !url.includes('//');
}

export function getEditFormURL(workspace: WorkspaceDto, form: StandardFormDto): string {
    return `/${workspace.workspaceName}/dashboard/forms/${form.formId}/edit`;
}
