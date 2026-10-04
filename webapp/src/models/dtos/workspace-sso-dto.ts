// Single sign-on administration (docs/sso.md); mirrors the backend's
// services/sso/connection_service.py DTOs.

export type SsoConnectionType = 'saml' | 'oidc';

export interface SsoConnectionDto {
    id: string;
    type: SsoConnectionType;
    name: string;
    status: 'enabled' | 'disabled';
    idpEntityId?: string | null;
    metadataUrl?: string | null;
    oidcDiscoveryUrl?: string | null;
    oidcClientId?: string | null;
    createdAt?: string | null;
    createdBy?: string | null;
    enabledAt?: string | null;
    tested: boolean;
    testedAt?: string | null;
    lastTestAt?: string | null;
    lastTestError?: string | null;
}

export interface SsoServiceProviderDto {
    acsUrl: string;
    entityId: string;
    spMetadataUrl: string;
    oidcRedirectUri: string;
}

export interface SsoSettingsDto {
    ssoRequired: boolean;
    ssoRequiredChangedAt?: string | null;
    defaultRole: string;
    assignableRoles: string[];
    ownerBreakGlass: boolean;
    revokedSessions?: number | null;
}

export interface SsoOverviewDto {
    available: boolean;
    serviceProvider?: SsoServiceProviderDto | null;
    domains: string[];
    connections: SsoConnectionDto[];
    settings: SsoSettingsDto;
    maxConnections: number;
    // the caller may change the configuration (the workspace owner only)
    canManage: boolean;
}

export interface CreateSsoConnectionRequest {
    type: SsoConnectionType;
    name?: string;
    metadataXml?: string;
    metadataUrl?: string;
    discoveryUrl?: string;
    clientId?: string;
    clientSecret?: string;
}

export interface UpdateSsoSettingsRequest {
    ssoRequired?: boolean;
    defaultRole?: string;
    revokeSessions?: boolean;
}
