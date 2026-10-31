export interface IGetWorkspaceFormQuery {
    workspace_id: string;
    custom_url: string;
    published?: boolean;
}

export interface IGetWorkspaceSubmissionQuery {
    workspace_id: string;
    submission_id: string;
}

export interface ISearchWorkspaceFormsQuery {
    workspace_id: string;
    query: string;
    published?: boolean;
}

export interface IPatchFormSettingsRequest {
    workspaceId: string;
    formId: string;
    body: any;
}

export interface IGetAllSubmissionsQuery {
    dataOwnerIdentifier?: string;
    workspaceId: string;
    email?: string;
    requestedForDeletionOly?: boolean;
    page?: number;
    data_subjects?: boolean;
    size?: number;
}

export interface IGetFormSubmissionsQuery extends IGetAllSubmissionsQuery {
    formId: string;
    /** Keyset paging with filters and sort: see the responses list endpoint (utils/response-list-state.ts). */
    paging?: 'keyset';
    sort_by?: 'created_at' | 'form_version';
    sort_order?: 'ASCENDING' | 'DESCENDING';
    /** UTC instants: from inclusive, to exclusive. */
    submittedFrom?: string;
    submittedTo?: string;
    status?: 'none' | 'pending' | 'declined';
    respondent?: 'anonymous' | 'known';
    formVersion?: number;
    cursor?: string;
}
