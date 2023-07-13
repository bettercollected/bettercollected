import React from 'react';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';

export interface IBuilderMenuState {
    spotlightField: { isOpen: boolean; afterFieldUuid: string };
    commands: { isOpen: boolean; afterFieldUuid: string };
    fieldSettings: { isOpen: boolean; atFieldUuid: string };
    pipingFields: { isOpen: boolean; atFieldUuid: string };
    pipingFieldSettings: { isOpen: boolean; uuid: string };
}

export interface IBuilderPipingState {}

export interface IBuilderStateVersion {
    timestamp: Date | string | number;
    fields: Record<string, IFormFieldState>;
}

export interface IBuilderState {
    id?: string;
    title: string;
    description?: string;
    menus?: IBuilderMenuState;
    piping?: IBuilderPipingState;
    fields: Record<string, IFormFieldState>;
    versions?: Array<IBuilderStateVersion>;
    currentVersionIndex?: number;
    isFormDirty?: boolean;
}

export interface IBuilderStateProps {
    builderState: IBuilderState;
    setBuilderState: React.Dispatch<React.SetStateAction<IBuilderState>> | ((state: IBuilderState) => Promise<void>);
}

export interface IFormFieldProperties {
    steps?: number;
    placeholder?: string;
    hidden?: boolean;
    allowMultipleSelection?: boolean;
    choices?: Record<string, { id: string; value: string }>;
}

export interface IFormFieldValidation {
    required: boolean;
}

export interface IFormFieldState {
    id: string;
    type: FormBuilderTagNames;
    label?: string;
    groupUuid?: string;
    hasPlaceholder?: boolean;
    isFocused?: boolean;
    isFieldActionMenuOpen?: boolean;
    isCommandMenuOpen?: boolean;
    properties?: IFormFieldProperties;
    cssProperties?: Record<string, string | number>;
    validations?: IFormFieldValidation;
}
