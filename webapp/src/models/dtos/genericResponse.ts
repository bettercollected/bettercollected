export interface IGenericAPIResponse<T> {
    apiVersion: string;
    payload: {
        content: T;
        pageable: {
            page: number;
            size: number;
            total: number;
        };
    };
    timestamp: Date;
}
