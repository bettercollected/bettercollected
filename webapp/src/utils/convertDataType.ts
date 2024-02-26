import { IFormTemplateDto } from '@app/models/dtos/template';

export const convertFormTemplateToStandardForm = (template: IFormTemplateDto) => {
    return {
        formId: '',
        title: template.title,
        description: template.description,
        buttonText: template.buttonText,
        groups: [],
        consent: [],
        fields: template.fields,
        coverImage: template.coverImage,
        logo: template.logo
    };
};