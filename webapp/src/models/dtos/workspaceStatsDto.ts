export interface WorkspaceStatsDto {
    forms: number;
    response: number;
    deletionRequests: {
        pending: number;
        success: number;
        total: number;
    };
}
