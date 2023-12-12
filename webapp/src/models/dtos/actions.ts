export interface Parameters {
    name: string;
    value: string;
    required?: boolean;
}

export enum Trigger {
    onSubmit = 'on_submit',
    onOpen = 'on_open'
}

export interface Action {
    id: string;
    actionCode?: string;
    parameters?: Array<Parameters>;
    secrets?: Array<Parameters>;
    name: string;
    title?: string;
    description?: string;
}
