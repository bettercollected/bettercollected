export interface FormStats {
    pageviews: {
        value: number;
        prev: number;
    };
    visitors: {
        value: number;
        prev: number;
    };
    visits: {
        value: number;
        prev: number;
    };
    bounces: {
        value: number;
        prev: number;
    };
    totaltime: {
        value: number;
        prev: number;
    };
}

export interface FormMetric {
    x: string;
    y: number;
}

export interface FormPageviews {
    pageviews: {
        x: string;
        y: number;
    }[];
    sessions: {
        x: string;
        y: number;
    }[];
}
