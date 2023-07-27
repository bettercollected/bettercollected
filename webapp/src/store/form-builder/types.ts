import { ActionCreatorWithPayload } from '@reduxjs/toolkit';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';

import { AppDispatch } from '../store';

export interface IBuilderMenuState {
    spotlightField?: { isOpen: boolean; afterFieldUuid: string };
    commands?: { isOpen: boolean; atFieldUuid: string; position: 'up' | 'down' };
    fieldSettings?: { isOpen: boolean; atFieldUuid: string };
    pipingFields?: { isOpen: boolean; atFieldUuid: string };
    pipingFieldSettings?: { isOpen: boolean; uuid: string };
}

export interface IBuilderPipingState {}

export interface IBuilderStateVersion {
    timestamp: Date | string | number;
    fields: Record<string, IFormFieldState>;
}

export interface IFormBuilderSettingsState {
    responseDataOwnerField?: string;
}

export interface IBuilderState {
    id?: string;
    title: string;
    description: string;
    menus?: IBuilderMenuState;
    piping?: IBuilderPipingState;
    fields: Record<string, IFormFieldState>;
    versions?: Array<IBuilderStateVersion>;
    currentVersionIndex?: number;
    settings?: IFormBuilderSettingsState;
    isFormDirty?: boolean;
    activeFieldIndex: number;
    activeFieldId: string;
}

export interface IBuilderStateProps {
    builderState: IBuilderState;
    setBuilderState: ActionCreatorWithPayload<Partial<IBuilderState>, 'builder/setBuilderState'>;
    dispatch: AppDispatch;
}

export interface IFormFieldProperties {
    steps?: number;
    placeholder?: string;
    hidden?: boolean;
    allowMultipleSelection?: boolean;
    choices?: Record<string, { id: string; value: string }>;
}

export interface IFormFieldValidation {
    required?: boolean;
    maxLength?: number;
    minLength?: number;
    maxValue?: number;
    minValue?: number;
    maxChoices?: number;
    minChoices?: number;
    regex?: string;
}

export interface IFormFieldState {
    id: string;
    type: FormBuilderTagNames;
    value?: string;
    groupUuid?: string;
    hasPlaceholder?: boolean;
    isFocused?: boolean;
    isFieldActionMenuOpen?: boolean;
    isCommandMenuOpen?: boolean;
    properties?: IFormFieldProperties;
    cssProperties?: Record<string, string | number>;
    validations?: IFormFieldValidation;
    position: number;
    replace?: boolean;
}

// Builder title and description DTO and Array
export interface IBuilderTitleAndDescriptionObj {
    id: string;
    tagName: string;
    type: FormBuilderTagNames;
    key: 'title' | 'description';
    position: number;
    placeholder: string;
    className: string;
}
