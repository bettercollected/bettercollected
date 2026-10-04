export interface WorkspaceMembersDto {
    id: string;
    firstName: string;
    lastName: string;
    roles: Array<string>;
    // OWNER, ADMIN, EDITOR, REVIEWER, VIEWER or PRIVACY_OFFICER
    role?: string | null;
    disabled?: boolean | null;
    // the account no longer exists: listed by id only
    accountDeleted?: boolean | null;
    joined: string;
    email: string;
    profileImage?: string;
    // 'sso' (just in time), 'scim' (the directory) or null (invited)
    provisionedBy?: string | null;
    // the workspace's SCIM directory controls this member's role and status
    managedByDirectory?: boolean;
}

export interface WorkspaceInvitationDto {
    token: any;
    expiryDate(createdAt: string, expiryDate: any): unknown;
    id: string;
    email: string;
    invitationStatus: string;
    invitationToken: string;
    role: string;
    updatedAt: string;
    createdAt: string;
    workspaceId: string;
    expiry: number;
    senderEmail?: string;
}
