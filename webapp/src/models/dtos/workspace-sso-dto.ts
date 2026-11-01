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
    // what the last failed test saw: the domain of the address the identity
    // provider sent (never the address) and the names of its claims
    lastTestDomain?: string | null;
    lastTestClaims?: string[] | null;
}

export interface SsoServiceProviderDto {
    acsUrl: string;
    entityId: string;
    spMetadataUrl: string;
    oidcRedirectUri: string;
}

// A workspace API key the owners review once single sign-on is required: keys
// are machine credentials and stay valid. No secret is ever part of it.
export interface SsoApiKeyDto {
    id: string;
    name: string;
    prefix: string;
    scopes: string[];
    createdBy?: string | null;
    // the creator's name (or address), when auth could say
    createdByLabel?: string | null;
    createdAt?: string | null;
    lastUsedAt?: string | null;
}

export interface SsoSettingsDto {
    ssoRequired: boolean;
    ssoRequiredChangedAt?: string | null;
    defaultRole: string;
    assignableRoles: string[];
    ownerBreakGlass: boolean;
    revokedSessions?: number | null;
    // with the requirement on: the live API keys created before it was switched on
    apiKeys?: SsoApiKeyDto[] | null;
    // with the requirement off: switching it on would refuse the caller's own session
    callerWouldBeLockedOut?: boolean;
}

export type SsoUnavailableReason = 'disabled' | 'not_configured';

export interface SsoOverviewDto {
    available: boolean;
    // why it is not available: SSO is switched off ("disabled") or on but not fully set up ("not_configured")
    reason?: SsoUnavailableReason | null;
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
    // the owner confirmed that their own session would be refused afterwards
    confirmLockout?: boolean;
}
