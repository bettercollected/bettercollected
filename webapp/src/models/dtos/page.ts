export interface Page<T> {
    items: Array<T>;
    page: number;
    pages: number;
    size: number;
    total: number;
    /** Keyset lists: false when `total` is a cap (a lower bound, "10,000+"). Absent: exact. */
    totalExact?: boolean;
    hasNext?: boolean;
    /** Signed handle on where this page begins, to send back for a page near it. */
    cursor?: string;
}
