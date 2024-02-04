import { StandardFormDto } from '@app/models/dtos/form';

export interface GroupInfoDto {
    name: string;
    description: string;
    emails?: Array<string>;
    formId?: string;
    regex?: string;
}

export interface ResponderGroupDto extends GroupInfoDto {
    id: string;
    forms: Array<StandardFormDto>;
}