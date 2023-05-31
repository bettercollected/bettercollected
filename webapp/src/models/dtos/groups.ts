export interface GroupInfoDto {
    name: string;
    description: string;
    email: string;
    emails: Array<string>;
}

export interface ResponderGroupDto {
    id: string;
    name: string;
    description: string;
    emails: Array<emailDto>;
}
export interface emailDto {
    identifier: string;
}
