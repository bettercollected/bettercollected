export interface WorkspaceDto {
    title: string;
    workspaceName: string;
    description: string;
    ownerId: string;
    profileImage: string;
    bannerImage: string;
    customDomain: string;
    theme: {
        primary_color: string;
        accent_color: string;
        text_color: string;
    };
    privacy_policy_url: string;
    terms_of_service_url: string;
    mailSettings: string;
    id: string;
}

export const initWorkspaceDto: WorkspaceDto = {
    title: '',
    workspaceName: '',
    description: '',
    ownerId: '',
    profileImage: '/favicon.ico',
    bannerImage: '/favicon.ico',
    customDomain: '',
    theme: {
        primary_color: '',
        accent_color: '',
        text_color: ''
    },
    privacy_policy_url: '',
    terms_of_service_url: '',
    mailSettings: '',
    id: ''
};
