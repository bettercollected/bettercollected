import React, { useCallback, useEffect } from 'react';

import { batch } from 'react-redux';

import useFormBuilderState from '@app/containers/form-builder/context';
import { setActiveChoice, setAddNewChoice, setAddNewField, setBuilderState, setDeleteChoice, setDeleteField, setUpdateField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IBuilderState, IFormFieldState } from '@app/store/form-builder/types';
import { useAppAsyncDispatch, useAppDispatch, useAppSelector } from '@app/store/hooks';
import { createNewChoice, createNewField, isMultipleChoice } from '@app/utils/formBuilderBlockUtils';

export default function MultipleChoiceKeyEventListener({ children }: React.PropsWithChildren) {
    const dispatch = useAppDispatch();
    const asyncDispatch = useAppAsyncDispatch();
    const { backspaceCount, setBackspaceCount } = useFormBuilderState();
    const builderState: IBuilderState = useAppSelector(selectBuilderState);

    const onKeyDownCallback = useCallback(
        (event: KeyboardEvent) => {
            batch(async () => {
                const fieldId = builderState.activeFieldId;
                const formField: IFormFieldState | undefined = builderState.fields[fieldId];
                if (!isMultipleChoice(formField?.type)) return;

                const choices = { ...formField.properties?.choices };

                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    //@ts-ignore
                    if ((formField.properties?.choices[formField.properties.activeChoiceId].value || '') !== '') {
                        event.stopPropagation();
                        //@ts-ignore
                        dispatch(setAddNewChoice(createNewChoice(formField.properties?.activeChoiceIndex + 1)));
                    } //@ts-ignore
                    else if (formField.properties?.choices[formField.properties.activeChoiceId].value === '' && Object.values(choices).length > 1) {
                        //@ts-ignore
                        dispatch(setDeleteChoice(formField.properties?.activeChoiceId));
                        dispatch(setAddNewField(createNewField(formField.position + 1)));
                        dispatch(
                            setBuilderState({
                                isFormDirty: true,
                                activeFieldIndex: formField.position + 1
                            })
                        );
                    } else {
                        event.preventDefault();
                        event.stopPropagation();

                        dispatch(setDeleteField(formField.id));
                        dispatch(setAddNewField(createNewField(formField.position)));
                    }
                } //@ts-ignore
                else if (event.key === 'ArrowDown' && formField.properties?.activeChoiceIndex < Object.values(formField.properties?.choices).length - 1) {
                    // event.stopPropagation();

                    dispatch(setActiveChoice({ position: (formField.properties?.activeChoiceIndex ?? 0) + 1 }));
                } //@ts-ignore
                else if (event.key === 'ArrowUp' && formField.properties?.activeChoiceIndex > 0) {
                    // event.stopPropagation();

                    dispatch(setActiveChoice({ position: (formField.properties?.activeChoiceIndex ?? 0) - 1 }));
                } else if (event.key === 'Backspace' && (!event.metaKey || !event.ctrlKey) && backspaceCount === 1 && Object.values(choices).length - 1 !== 0) {
                    event.preventDefault();
                    event.stopPropagation();

                    //@ts-ignore
                    asyncDispatch(dispatch(setDeleteChoice(formField.properties?.activeChoiceId))).then(() => setBackspaceCount(0));
                    dispatch(setActiveChoice({ position: (formField.properties?.activeChoiceIndex ?? 0) - 1 }));
                }
            });
        },

        [asyncDispatch, backspaceCount, builderState.activeFieldId, builderState.fields, dispatch, setBackspaceCount]
    );

    useEffect(() => {
        document.addEventListener('keydown', onKeyDownCallback);

        return () => {
            document.removeEventListener('keydown', onKeyDownCallback);
        };
    }, [builderState, backspaceCount, onKeyDownCallback]);

    return <div>{children}</div>;
}
