import React, { useCallback, useEffect } from 'react';

import { batch } from 'react-redux';
import { toast } from 'react-toastify';
import { v4 } from 'uuid';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import useFormBuilderState from '@app/containers/form-builder/context';
import eventBus from '@app/lib/event-bus';
import EventBusEventType from '@app/models/enums/eventBusEnum';
import { FormBuilderTagNames, NonInputFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addDuplicateField, resetBuilderMenuState, setAddNewField, setBuilderState, setDeleteField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IBuilderState, IFormFieldState } from '@app/store/form-builder/types';
import { useAppAsyncDispatch, useAppDispatch, useAppSelector } from '@app/store/hooks';
import { createNewField, isMultipleChoice } from '@app/utils/formBuilderBlockUtils';

export default function FormBuilderKeyListener({ children }: React.PropsWithChildren) {
    const dispatch = useAppDispatch();
    const asyncDispatch = useAppAsyncDispatch();
    const { backspaceCount, setBackspaceCount } = useFormBuilderState();

    const builderState: IBuilderState = useAppSelector(selectBuilderState);
    const fullScreenModal = useFullScreenModal();
    const modal = useModal();

    const onKeyDownCallback = useCallback(
        (event: KeyboardEvent) => {
            batch(async () => {
                const fieldId = builderState.activeFieldId;
                const focusNextField = () => {
                    let nextFieldId = Object.keys(builderState.fields)[builderState.activeFieldIndex + 1];

                    if (isMultipleChoice(builderState.fields[nextFieldId]?.type)) {
                        const choicesKeys = Object.keys(builderState.fields[nextFieldId].properties?.choices ?? {});
                        const firstChoiceKey = choicesKeys[0];
                        document.getElementById(`choice-${firstChoiceKey}`)?.focus();
                    }
                    if (builderState.activeFieldIndex === -2) nextFieldId = 'form-description';
                    document.getElementById(`item-${nextFieldId}`)?.focus();
                };

                const focusPreviousField = () => {
                    let previousFieldId = Object.keys(builderState.fields)[builderState.activeFieldIndex - 1];
                    if (isMultipleChoice(builderState.fields[previousFieldId]?.type)) {
                        const choicesKeys = Object.keys(builderState.fields[previousFieldId].properties?.choices ?? {});
                        const lastChoiceKey = choicesKeys[choicesKeys.length - 1];
                        document.getElementById(`choice-${lastChoiceKey}`)?.focus();
                    }
                    if (builderState.activeFieldIndex === 0) previousFieldId = 'form-description';
                    if (builderState.activeFieldIndex === -1) previousFieldId = 'form-title';

                    document.getElementById(`item-${previousFieldId}`)?.focus();
                };

                if (event.key === 'Escape') {
                    dispatch(resetBuilderMenuState());
                } else if (builderState.menus?.commands?.isOpen || fullScreenModal.isOpen || modal.isOpen || builderState.menus?.spotlightField?.isOpen) {
                    return;
                } else if (event.key === 'Enter' && !event.shiftKey && builderState.activeFieldIndex >= -1) {
                    event.preventDefault();

                    const newField = createNewField(builderState.activeFieldIndex);
                    if (builderState.activeFieldIndex >= 0 || Object.keys(builderState.fields).length === 0) {
                        if (NonInputFormBuilderTagNames.includes(builderState.fields[builderState.activeFieldId]?.type) && Object.values(builderState.fields)[builderState.activeFieldIndex + 1]?.type.includes('input_')) {
                            focusNextField();
                            return;
                        }
                        dispatch(setAddNewField(newField));
                        setTimeout(() => document.getElementById(`item-${newField.id}`)?.focus(), 1);
                    } else {
                        document.getElementById(`item-${Object.keys(builderState.fields)[0]}`)?.focus();
                    }
                } else if (event.key === 'Tab' || (event.shiftKey && event.key === 'Tab')) event.preventDefault();
                else if (!event.ctrlKey && !event.metaKey && (event.key === 'ArrowDown' || (event.key === 'Enter' && builderState.activeFieldIndex < -1)) && builderState.activeFieldIndex < Object.keys(builderState.fields).length - 1) {
                    focusNextField();
                } else if (!event.ctrlKey && !event.metaKey && event.key === 'ArrowUp' && builderState.activeFieldIndex > -2) {
                    focusPreviousField();
                } else if (event.code === 'Slash' && builderState.activeFieldIndex >= 0 && !event.shiftKey && builderState.fields[builderState.activeFieldId]?.type === FormBuilderTagNames.LAYOUT_SHORT_TEXT) {
                    eventBus.emit(EventBusEventType.FormBuilder.OpenTagSelector, event);
                } else if (event.key === 'Backspace' && (!event.metaKey || !event.ctrlKey) && builderState.activeFieldIndex >= 0) {
                    if (builderState.fields[builderState.activeFieldId].type === FormBuilderTagNames.CONDITIONAL) return;
                    if (backspaceCount === 1) {
                        event.preventDefault();
                        asyncDispatch(setDeleteField(fieldId)).then(() => setBackspaceCount(0));
                        focusPreviousField();
                    } else {
                        setBackspaceCount(1);
                    }
                } else if (((event.key === 'Delete' && event.ctrlKey) || (event.key === 'Backspace' && event.metaKey)) && fieldId) {
                    event.preventDefault();
                    event.stopPropagation();

                    if (builderState.activeFieldIndex < 0) {
                        toast("Can't delete the form title and description", { type: 'warning' });
                    } else dispatch(setDeleteField(fieldId));

                    focusPreviousField();
                } else if ((event.key === 'D' || event.key === 'd') && !event.shiftKey && (event.ctrlKey || event.metaKey) && fieldId) {
                    event.preventDefault();
                    event.stopPropagation();
                    if (builderState.activeFieldIndex < 0) {
                        toast("Can't duplicate the form title and description", { type: 'warning' });
                    } else {
                        const formField = builderState.fields[fieldId];
                        const newField: IFormFieldState = { ...formField };
                        newField.id = v4();
                        newField.position = builderState.activeFieldIndex + 1;
                        dispatch(addDuplicateField(newField));
                        dispatch(setBuilderState({ isFormDirty: true }));
                    }
                } else if ((event.key === 'I' || event.key === 'i') && !event.shiftKey && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();
                    event.stopPropagation();

                    asyncDispatch(resetBuilderMenuState()).then(() => {
                        modal.openModal('FORM_BUILDER_ADD_FIELD_VIEW');
                    });
                } else if ((event.key === 'S' || event.key === 's') && !event.shiftKey && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();
                    event.stopPropagation();

                    // eventBus.emit(EventBusEventType.FormBuilder.Save);
                } else if ((event.key === 'P' || event.key === 'p') && !event.shiftKey && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();
                    event.stopPropagation();

                    eventBus.emit(EventBusEventType.FormBuilder.Preview);
                }
            });
        },
        [builderState.activeFieldId, builderState.fields, builderState.menus?.commands?.isOpen, builderState.menus?.spotlightField?.isOpen, builderState.activeFieldIndex, fullScreenModal.isOpen, modal, backspaceCount]
    );

    useEffect(() => {
        document.addEventListener('keydown', onKeyDownCallback);

        return () => {
            document.removeEventListener('keydown', onKeyDownCallback);
        };
    }, [builderState, backspaceCount, onKeyDownCallback]);

    return <div>{children}</div>;
}
