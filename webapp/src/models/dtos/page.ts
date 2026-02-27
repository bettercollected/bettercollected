export interface Page<T> {
    items: Array<T>;
    page: number;
    pages: number;
    size: number;
    total: number;
}
