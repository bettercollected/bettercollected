export interface WorkspaceMembersDto {
    id: string;
    firstName: string;
    lastName: string;
    roles: Array<string>;
    joined: string;
    email: string;
    profileImage?: string;
}

export interface WorkspaceInvitationDto {
    id: string;
    email: string;
    invitationStatus: string;
    invitationToken: string;
    role: string;
    updatedAt: string;
    createdAt: string;
    workspaceId: string;
    expiry: number;
}
