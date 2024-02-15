interface StandardForm {
    formId: string
    title: string
    description: string
    buttonText?: string
    version?: number;
    settings?: {
        pinned: boolean;
        embedUrl?: string;
        customUrl: string;
        responseDataOwnerField?: string;
        private?: boolean;
        provider: string;
        isPublished?: boolean;
        privacyPolicyUrl?: string;
        responseExpiration?: string;
        disableBranding: boolean;
        hidden: boolean;
        formCloseDate?: string;
        requireVerifiedIdentity?: boolean;
        showSubmissionNumber?: boolean;
    };
    fields: Array<FormField>
}

interface FormField {
    index: number
    id: string
    properties?: FormFieldProperties
    validations?: FieldValidations
    title?: string
    description?: string
    type?: any
    value?: string
}


interface FieldValidations {
    required?: boolean
    maxLength?: number
    minLength?: number
    minValue?: number
    mazValue?: number
    regex?: number
    minChoice?: number
    maxChoices?: number
}

interface FormFieldProperties {
    hidden?: boolean
    fields: Array<FieldChoice>
    placeholder?: string
    choices?: Array<any>
    steps?: number
    startFrom?: number
    ratingShape?: string
    dateFormat?: string
}

interface FieldChoice {
    id: string
    value?: string
    label?: string
}