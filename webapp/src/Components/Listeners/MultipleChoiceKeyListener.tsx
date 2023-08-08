import React, { useCallback, useEffect } from 'react';

import useFormBuilderState from '@app/containers/form-builder/context';
import { setActiveChoice, setAddNewChoice, setDeleteChoice, setDeleteField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IBuilderState, IFormFieldState } from '@app/store/form-builder/types';
import { useAppAsyncDispatch, useAppDispatch, useAppSelector } from '@app/store/hooks';
import { isMultipleChoice } from '@app/utils/formBuilderBlockUtils';

export default function MultipleChoiceKeyEventListener({ children }: React.PropsWithChildren) {
    const dispatch = useAppDispatch();
    const asyncDispatch = useAppAsyncDispatch();
    const { backspaceCount, setBackspaceCount } = useFormBuilderState();
    const builderState: IBuilderState = useAppSelector(selectBuilderState);

    const onKeyDownCallback = useCallback(
        (event: KeyboardEvent) => {
            const fieldId = builderState.activeFieldId;
            const formField: IFormFieldState | undefined = builderState.fields[fieldId];
            if (!isMultipleChoice(formField?.type)) return;

            const choices = { ...formField.properties?.choices };

            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();

                //@ts-ignore
                if ((formField.properties?.choices[formField.properties.activeChoiceId].value || '') !== '') {
                    event.stopPropagation();

                    dispatch(setAddNewChoice());
                } else {
                    if (formField.properties?.activeChoiceId && Object.values(choices).length - 1 !== 0) {
                        event.stopPropagation();
                        dispatch(setDeleteChoice(formField.properties?.activeChoiceId));
                    } else {
                        dispatch(setDeleteField(formField.id));
                    }
                }
            } else if (event.key === 'ArrowDown') {
                //@ts-ignore
                if (formField.properties?.activeChoiceIndex < Object.values(formField.properties?.choices).length - 1) {
                    event.stopPropagation();
                    dispatch(setActiveChoice({ position: (formField.properties?.activeChoiceIndex ?? 0) + 1 }));
                }
            } else if (event.key === 'ArrowUp') {
                //@ts-ignore
                if (formField.properties?.activeChoiceIndex > 0) {
                    event.stopPropagation();
                    dispatch(setActiveChoice({ position: (formField.properties?.activeChoiceIndex ?? 0) - 1 }));
                }
            } else if (event.key === 'Backspace' && (!event.metaKey || !event.ctrlKey)) {
                if (backspaceCount === 1 && Object.values(choices).length - 1 !== 0) {
                    event.preventDefault();
                    event.stopPropagation();

                    //@ts-ignore
                    asyncDispatch(dispatch(setDeleteChoice(formField.properties?.activeChoiceId))).then(() => setBackspaceCount(0));
                    dispatch(setActiveChoice({ position: (formField.properties?.activeChoiceIndex ?? 0) - 1 }));
                } else {
                    setBackspaceCount(1);
                }
            }
        },

        // eslint-disable-next-line react-hooks/exhaustive-deps
        [asyncDispatch, backspaceCount, builderState.activeFieldId, builderState.activeFieldIndex, builderState.fields, dispatch, setBackspaceCount]
    );

    useEffect(() => {
        document.addEventListener('keydown', onKeyDownCallback);

        return () => {
            document.removeEventListener('keydown', onKeyDownCallback);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [builderState, backspaceCount]);

    return <div>{children}</div>;
}
