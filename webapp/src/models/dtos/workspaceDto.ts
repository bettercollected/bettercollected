export interface WorkspaceDto {
    title: string;
    workspaceName: string;
    description: string;
    ownerId: string;
    profileImage?: string;
    bannerImage?: string;
    customDomain?: string;
    dashboardAccess?: string;
    default?: string;
    disabled?: string;
    theme?: {
        primary_color: string;
        accent_color: string;
        text_color: string;
    };
    privacy_policy_url: string;
    terms_of_service_url: string;
    mailSettings?: string | null;
    id: string;
    isPro?: boolean;
}

export const initWorkspaceDto: WorkspaceDto = {
    title: 'My title',
    workspaceName: 'ankit-sapkota',
    description: 'Description',
    ownerId: '63ca5518b613f81e118e3d8c',
    profileImage: '',
    bannerImage: '',
    customDomain: '',
    theme: {
        primary_color: '',
        accent_color: '',
        text_color: ''
    },
    privacy_policy_url: 'https://bettercollected.com/legal/privacy-policy-2022.pdf',
    terms_of_service_url: 'https://bettercollected.com/legal/terms-and-conditions-2022.pdf',
    mailSettings: '',
    id: '63ca5518b613f81e118e3d8d',
    isPro: false
};
