import { StandardFormFieldDto } from '@app/models/dtos/form';
import { TemplateCategory } from '@app/models/enums/template';

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
}