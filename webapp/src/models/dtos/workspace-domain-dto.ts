// Mirrors the backend's WorkspaceDomainDto (docs/verified-domains.md).
export type WorkspaceDomainStatus = 'pending' | 'verified' | 'failed' | 'conflict';

export interface WorkspaceDomainDto {
    id: string;
    domain: string; // ASCII (punycode), what DNS uses
    displayDomain: string; // Unicode
    status: WorkspaceDomainStatus;
    txtRecordName: string;
    txtRecordValue: string;
    createdAt?: string | null;
    createdBy?: string | null;
    verifiedAt?: string | null;
    lastCheckedAt?: string | null;
    lastCheckError?: string | null;
    failedChecks: number;
    verificationLostAt?: string | null;
}
