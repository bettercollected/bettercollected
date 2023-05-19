import environments from '@app/configs/environments';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

export const getFormUrl = (form: StandardFormDto, workspace: WorkspaceDto) => {
    const isCustomDomain = window?.location.host !== environments.CLIENT_DOMAIN;
    const slug = form.settings?.customUrl;
    let shareUrl = '';
    if (window && typeof window !== 'undefined') {
        const scheme = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://`;
        const domainHost = isCustomDomain ? `${workspace.customDomain}/forms/${slug}` : `${environments.CLIENT_DOMAIN}/${workspace.workspaceName}/forms/${slug}`;
        shareUrl = scheme + domainHost;
    }
    return shareUrl;
};
