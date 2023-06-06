export interface GroupInfoDto {
    name: string;
    description: string;
    email: string;
    emails: Array<string>;
}

export interface ResponderGroupDto extends GroupInfoDto {
    id: string;
    forms: Array<FormInfoDto>;
}

export interface FormInfoDto {
    form_id: string;
}
