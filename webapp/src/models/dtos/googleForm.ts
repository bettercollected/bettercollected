export interface GoogleFormDto {
    formId: string;
    info: {
        title: string;
        description?: string;
        documentTitle?: string;
    };
    responderUri: string;
    revisionId: string;
    items: Array<{
        itemId: string;
        title: string;
        /** Save for customize data */
        [prop: string]: any;
    }>;

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
