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
    // the creator's name, only for a current member and when auth could say (never an address)
    createdByLabel?: string | null;
    // the creator is no longer a member of the workspace
    createdByFormerMember?: boolean;
    createdAt?: string | null;
    lastUsedAt?: string | null;
    // created after the requirement was switched on
    createdAfterRequirement?: boolean;
}

// An owner break-glass entry (docs/sso.md): ids only; the name is a current member's.
export interface SsoAuditEntryDto {
    id: string;
    event: 'sso_break_glass_request' | 'sso_break_glass_sign_in' | string;
    at?: string | null;
    userId: string;
    userLabel?: string | null;
    userIsMember?: boolean;
    sessionId?: string | null;
    // request entries: the HTTP method and the route's path template (never a concrete id or query)
    method?: string | null;
    path?: string | null;
}

// One page of the break-glass log, newest first; nextCursor asks for the older one.
export interface SsoAuditPageDto {
    entries: SsoAuditEntryDto[];
    nextCursor?: string | null;
}

export interface SsoSettingsDto {
    ssoRequired: boolean;
    ssoRequiredChangedAt?: string | null;
    defaultRole: string;
    assignableRoles: string[];
    ownerBreakGlass: boolean;
    revokedSessions?: number | null;
    // with the requirement on: all live API keys (the newer ones are flagged)
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
    // the latest owner break-glass entries, newest first
    audit?: SsoAuditEntryDto[];
    auditNextCursor?: string | null;
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
