// SCIM directory sync (docs/sso.md, "Directory sync"); mirrors the backend's
// services/scim/directory_service.py DTOs.

export interface ScimDirectoryDto {
    id: string;
    type: string;
    typeLabel: string;
    name: string;
    scimEndpoint: string;
    createdAt?: string | null;
    createdBy?: string | null;
    rotatedAt?: string | null;
    lastEventAt?: string | null;
    lastEventType?: string | null;
    lastResyncAt?: string | null;
    lastResyncSummary?: Record<string, number> | null;
    lastResyncError?: string | null;
}

// Returned by create and rotate only: the token is never shown again.
export interface ScimCredentialsDto {
    directory: ScimDirectoryDto;
    scimEndpoint: string;
    bearerToken: string;
}

export interface ScimGroupDto {
    id: string;
    name: string;
    role?: string | null;
    members: number;
}

export interface ScimIssueDto {
    email: string;
    state: 'failed' | 'ignored';
    reason: string;
    message: string;
    at?: string | null;
}

export interface ScimOverviewDto {
    available: boolean;
    hasVerifiedDomain: boolean;
    directory?: ScimDirectoryDto | null;
    types: { type: string; label: string }[];
    counts: Record<string, number>;
    issues: ScimIssueDto[];
    groups: ScimGroupDto[];
    defaultRole: string;
    mappableRoles: string[];
    canManage: boolean;
}

export interface CreateScimDirectoryRequest {
    type: string;
    name?: string;
}

export interface ScimResyncDto {
    directory: ScimDirectoryDto;
    summary: Record<string, number>;
}
