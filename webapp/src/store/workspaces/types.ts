export interface IGetWorkspaceFormQuery {
    workspace_id: string;
    custom_url: string;
}

export interface IGetWorkspaceSubmissionQuery {
    workspace_id: string;
    submission_id: string;
}

export interface ISearchWorkspaceFormsQuery {
    workspace_id: string;
    query: string;
}

export interface IPatchFormSettingsRequest {
    workspaceId: string;
    formId: string;
    body: any;
}

export interface IGetAllSubmissionsQuery {
    workspaceId: string;
    requestedForDeletionOly?: boolean;
    page?: number;
    data_subjects?: boolean;
    size?: number;
}

export interface IGetFormSubmissionsQuery extends IGetAllSubmissionsQuery {
    formId: string;
}
