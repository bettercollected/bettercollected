export interface IGetWorkspaceFormQuery {
    workspace_id: string;
    custom_url: string;
}

export interface IGetWorkspaceFileUrlQuery {
    workspace_id: string;
    file_id: string;
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
}
