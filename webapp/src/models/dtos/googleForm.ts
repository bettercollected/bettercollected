export interface GoogleFormDto {
    id: string;
    info: {
        title: string;
        description?: string;
        documentTitle?: string;
    };
    responderUri: string;

    /** Save for customize data */
    [prop: string]: any;
}

export interface GoogleMinifiedFormDto {
    id: string;
    name: string;
    webViewLink: string;
    iconLink: string;
    createdTime: string;
    modifiedTime: string;
    owners: Array<{ kind: string; displayName: string; photoLink: string; me: boolean; permissionId: string; emailAddress: string }>;
}
