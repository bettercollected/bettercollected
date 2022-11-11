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
