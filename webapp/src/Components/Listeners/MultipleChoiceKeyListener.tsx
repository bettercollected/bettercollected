import React, { useCallback, useEffect } from 'react';

import { batch } from 'react-redux';

import useFormBuilderState from '@app/containers/form-builder/context';
import { setActiveChoice, setAddNewChoice, setAddNewField, setBuilderState, setDeleteChoice, setDeleteField, setUpdateField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IBuilderState, IFormFieldState } from '@app/store/form-builder/types';
import { useAppAsyncDispatch, useAppDispatch, useAppSelector } from '@app/store/hooks';
import { createNewChoice, createNewField, isMultipleChoice } from '@app/utils/formBuilderBlockUtils';

export default function MultipleChoiceKeyEventListener({ children, field }: { children: React.ReactNode; field: IFormFieldState }) {
    const dispatch = useAppDispatch();
    const asyncDispatch = useAppAsyncDispatch();
    const { backspaceCount, setBackspaceCount } = useFormBuilderState();
    const builderState: IBuilderState = useAppSelector(selectBuilderState);

    const onKeyDownCallback = useCallback(
        (event: KeyboardEvent) => {
            batch(async () => {
                const fieldId = builderState.activeFieldId;
                const formField: IFormFieldState | undefined = builderState.fields[fieldId];
                if (fieldId !== field.id) return;
                if (!isMultipleChoice(formField?.type)) return;
                const { activeChoiceId, activeChoiceIndex } = builderState;
                const { choices } = formField.properties || {};
                if (activeChoiceIndex === undefined || activeChoiceId === undefined || choices === undefined) return;
                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    event.stopPropagation();
                    if (choices[activeChoiceId].value !== '') {
                        const newChoice = createNewChoice(activeChoiceIndex + 1);
                        dispatch(setAddNewChoice(newChoice));
                        console.log('newChoice', newChoice);

                        setTimeout(() => document.getElementById(`choice-${newChoice.id}`)?.focus(), 1);
                    } else if (choices[activeChoiceId].value === '' && Object.values(choices).length > 1) {
                        dispatch(setDeleteChoice(activeChoiceId));
                        const newField = createNewField(formField.position + 1);
                        dispatch(setAddNewField(newField));
                        setTimeout(() => document.getElementById(`item-${newField.id}`)?.focus(), 1);
                    } else {
                        const newField = createNewField(formField.position);
                        dispatch(setDeleteField(formField.id));
                        dispatch(setAddNewField(newField));
                        setTimeout(() => document.getElementById(`item-${newField.id}`)?.focus(), 1);
                    }
                } else if (event.key === 'ArrowDown' && activeChoiceIndex < Object.values(choices).length - 1) {
                    event.stopPropagation();
                    document.getElementById(`choice-${Object.keys(choices)[activeChoiceIndex + 1]}`)?.focus();
                } else if (event.key === 'ArrowUp' && activeChoiceIndex > 0) {
                    event.stopPropagation();
                    document.getElementById(`choice-${Object.keys(choices)[activeChoiceIndex - 1]}`)?.focus();
                } else if (event.key === 'Backspace' && (!event.metaKey || !event.ctrlKey) && backspaceCount === 1 && Object.values(choices).length - 1 !== 0) {
                    event.preventDefault();
                    event.stopPropagation();

                    asyncDispatch(dispatch(setDeleteChoice(activeChoiceId))).then(() => setBackspaceCount(0));
                    document.getElementById(`choice-${Object.keys(choices)[activeChoiceIndex - 1]}`)?.focus();
                }
            });
        },

        [asyncDispatch, backspaceCount, builderState.activeFieldId, builderState.fields, dispatch, setBackspaceCount]
    );

    useEffect(() => {
        if (field.id === builderState.activeFieldId) document.addEventListener('keydown', onKeyDownCallback);
        return () => {
            document.removeEventListener('keydown', onKeyDownCallback);
        };
    }, [builderState, backspaceCount, onKeyDownCallback, builderState.activeFieldId, builderState.fields]);

    return <div>{children}</div>;
}
