export interface IGetTemplate {
    workspace_id?: string;
    template_id: string;
}

export interface ICreateTemplateFromForm {
    workspace_id: string;
    form_id: string;
}

export interface ICreateFormFromTemplate {
    workspace_id: string;
    template_id: string;
}
