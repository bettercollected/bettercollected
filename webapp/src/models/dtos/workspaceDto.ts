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
