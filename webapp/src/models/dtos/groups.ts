export interface GroupInfoDto {
    name: string;
    description: string;
    email: string;
    emails: Array<string>;
}

export interface ResponderGroupDto extends GroupInfoDto {
    id: string;
}
