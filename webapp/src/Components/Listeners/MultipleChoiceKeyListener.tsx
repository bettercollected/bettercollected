import React, { useCallback, useEffect } from 'react';

import { batch } from 'react-redux';

import useFormBuilderState from '@app/containers/form-builder/context';
import { setAddNewChoice, setAddNewField, setDeleteChoice, setDeleteField } from '@app/store/form-builder/actions';
import { selectActiveChoiceId, selectActiveChoiceIndex, selectActiveFieldId, selectFormField } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppAsyncDispatch, useAppDispatch, useAppSelector } from '@app/store/hooks';
import { createNewChoice, createNewField, isMultipleChoice } from '@app/utils/formBuilderBlockUtils';

export default function MultipleChoiceKeyEventListener({ children, field }: { children: React.ReactNode; field: IFormFieldState }) {
    const dispatch = useAppDispatch();
    const asyncDispatch = useAppAsyncDispatch();
    const { backspaceCount, setBackspaceCount } = useFormBuilderState();

    const activeFieldId = useAppSelector(selectActiveFieldId);
    const formField = useAppSelector(selectFormField(field.id));
    const activeChoiceId = useAppSelector(selectActiveChoiceId);
    const activeChoiceIndex = useAppSelector(selectActiveChoiceIndex);

    const onKeyDownCallback = useCallback(
        (event: KeyboardEvent) => {
            batch(async () => {
                if (activeFieldId !== field.id) return;
                if (!isMultipleChoice(formField?.type)) return;
                const { choices } = formField.properties || {};
                if (activeChoiceIndex === undefined || activeChoiceId === undefined || choices === undefined) return;
                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    event.stopPropagation();
                    if (choices[activeChoiceId].value !== '') {
                        const newChoice = createNewChoice(activeChoiceIndex + 1);
                        const choice = {
                            fieldId: formField.id,
                            choice: newChoice
                        };
                        dispatch(setAddNewChoice(choice));
                        setTimeout(() => document.getElementById(`choice-${newChoice.id}`)?.focus(), 1);
                    } else if (choices[activeChoiceId].value === '' && Object.values(choices).length > 1) {
                        dispatch(setDeleteChoice(activeChoiceId));
                        const newField = createNewField(formField.position);
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

        [backspaceCount, activeFieldId, activeChoiceId, setBackspaceCount, field]
    );

    useEffect(() => {
        if (field.id === activeFieldId) document.addEventListener('keydown', onKeyDownCallback);
        return () => {
            document.removeEventListener('keydown', onKeyDownCallback);
        };
    }, [backspaceCount, activeFieldId, activeChoiceId, field]);

    return <div>{children}</div>;
}
