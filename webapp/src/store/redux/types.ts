import { StandardFormFieldDto } from '@app/models/dtos/form';

export interface IFormTemplateSettings {
    isPublic: boolean;
}

export interface IFormTemplateDto {
    previewImage: string;
    id: string;
    workspaceId: string;
    type: string;
    title: string;
    description: string;
    logo: string;
    coverImage: string;
    category: TemplateCategory;
    buttonText: string;
    fields: Array<StandardFormFieldDto>;
    settings: IFormTemplateSettings;
    createdBy: string;
    importedFrom: string;
    welcomePage: any;
    thankyouPage: any;
    theme: any;
}

export enum TemplateCategory {
    Survey = 'SURVEY'
}

export interface ICreateTemplateFromForm {
    workspace_id: string;
    form_id: string;
}

export interface ICreateFormFromTemplate {
    workspace_id: string;
    template_id: string;
}
