// What the audit log routes answer (backend app/models/dtos/audit_log_dto.py, docs/audit-log.md). Codes, ids and
// enum values only: the dashboard words each entry in the reader's language and never shows the id of a person, form or response. A field the
// server leaves out (a session id for a Privacy officer, a response id for someone who may not open it) is absent.

/** The areas the Type filter offers, in order (the server's catalogue). */
export const AUDIT_AREAS = ['access', 'members', 'forms', 'responses', 'api_keys', 'integrations', 'security'] as const;
export type AuditArea = (typeof AUDIT_AREAS)[number];

export interface AuditEntryDto {
    id: string;
    /** A code of the server's catalogue; one this dashboard does not know gets a neutral sentence. */
    event: string;
    area?: string;
    at: string;
    actorId?: string | null;
    sessionId?: string | null;
    targetUserId?: string | null;
    toUserId?: string | null;
    formId?: string | null;
    responseId?: string | null;
    revision?: number | null;
    groupId?: string | null;
    grantRole?: string | null;
    grantExport?: boolean | null;
    accessMode?: string | null;
    // team_linked: a directory group was linked to the team (groupId), or unlinked from it
    linked?: boolean | null;
    scimGroupId?: string | null;
    role?: string | null;
    previousRole?: string | null;
    count?: number | null;
    required?: boolean | null;
    exportChannel?: string | null;
    exportFormat?: string | null;
    keyId?: string | null;
    reason?: string | null;
    keyRole?: string | null;
    keyRoleBefore?: string | null;
    formScope?: string | null;
    widened?: boolean | null;
    /** Settings entries: the kind of single sign-on connection or directory, an on/off setting's new value, the AI provider's id (never shown). */
    connectionType?: string | null;
    directoryType?: string | null;
    enabled?: boolean | null;
    provider?: string | null;
    /** `audit_retention_changed`: how many months entries are kept now and before (whole numbers, never a name). */
    retentionMonths?: number | null;
    previousRetentionMonths?: number | null;
    /** Integration entries: which parts of the configuration changed, by a fixed vocabulary (never their content). */
    changed?: string[] | null;
    /** `report_view_*`: the saved report view (its id) and its scope, `private` or `form`; never its name or definition. */
    viewId?: string | null;
    viewScope?: string | null;
    method?: string | null;
    path?: string | null;
}

/** `former`: no longer a member (no name is sent); `member` with no name: the name could not be looked up. */
export interface AuditMemberLabel {
    status: 'member' | 'former' | string;
    name?: string | null;
}

export interface AuditFormLabel {
    status: 'available' | 'gone' | string;
    title?: string | null;
}

export interface AuditTeamLabel {
    status: 'available' | 'gone' | string;
    name?: string | null;
}

export interface AuditLabels {
    members: Record<string, AuditMemberLabel>;
    forms: Record<string, AuditFormLabel>;
    teams: Record<string, AuditTeamLabel>;
}

export interface AuditPageDto {
    entries: AuditEntryDto[];
    nextCursor?: string | null;
    labels?: Partial<AuditLabels>;
    /** How many days an entry is kept (the page states it). */
    retentionDays?: number;
}

/** How long this workspace keeps its entries (backend `AuditRetentionDto`, docs/audit-log.md). */
export interface AuditRetentionDto {
    months: number;
    days: number;
    /** The choices, shortest first; none is shorter than `minimumMonths`. */
    options: number[];
    minimumMonths: number;
    defaultMonths: number;
    /** Only an owner changes it. */
    canChange: boolean;
    /** Set by a change that shortened the period: entries past it go at the next daily clean-up, not at once. */
    appliesAtNextPurge?: boolean;
}
