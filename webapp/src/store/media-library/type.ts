export interface MediaLibrary {
    mediaUrl: string;
    mediaName: string;
    mediaType: string;
    mediaId: string;
    workspaceId: string;
}

export interface MediaLibraryRequestDto {
    workspace_id: string;
    media_query?: string;
}

export interface MediaLibraryPostRequestDto extends MediaLibraryRequestDto {
    media: any;
}

export interface MediaLibraryDeleteRequestDto extends MediaLibraryRequestDto {
    media_id: string;
}
