import React, { useEffect } from 'react';

import { setActiveChoice, setAddNewChoice, setAddNewField, setBuilderState, setDeleteChoice, setDeleteField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IBuilderState, IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { createNewField, isMultipleChoice } from '@app/utils/formBuilderBlockUtils';

export default function MultipleKeyEventListener({ children }: React.PropsWithChildren) {
    const dispatch = useAppDispatch();
    const builderState: IBuilderState = useAppSelector(selectBuilderState);

    const onKeyDownCallback = (event: KeyboardEvent) => {
        const fieldId = builderState.activeFieldId;
        const formField: IFormFieldState | undefined = builderState.fields[fieldId];

        if (!isMultipleChoice(formField?.type)) return;
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            event.stopPropagation();
            if (builderState.activeFieldIndex >= -1) {
                //@ts-ignore
                if ((formField.properties?.choices[formField.properties.activeChoiceId].value || '') !== '') {
                    dispatch(setAddNewChoice());
                } else {
                    const choices = { ...formField.properties?.choices };
                    if (formField.properties?.activeChoiceId) dispatch(setDeleteChoice(formField.properties?.activeChoiceId));
                    if (Object.values(choices).length - 1 === 0) dispatch(setDeleteField(formField.id));
                    dispatch(setAddNewField(createNewField(builderState.activeFieldIndex)));
                    dispatch(
                        setBuilderState({
                            isFormDirty: true,
                            activeFieldIndex: builderState.activeFieldIndex + (Object.values(choices).length - 1 === 0 ? 0 : 1)
                        })
                    );
                }
            }
        }
        if (event.key === 'ArrowDown') {
            //@ts-ignore
            if (formField.properties?.activeChoiceIndex < Object.values(formField.properties?.choices).length - 1) {
                dispatch(setActiveChoice({ position: (formField.properties?.activeChoiceIndex ?? 0) + 1 }));
            }
        }
        if (event.key === 'ArrowUp') {
            //@ts-ignore
            if (formField.properties?.activeChoiceIndex > 0) {
                dispatch(setActiveChoice({ position: (formField.properties?.activeChoiceIndex ?? 0) - 1 }));
            }
        }

        event.stopPropagation();
    };

    useEffect(() => {
        document.addEventListener('keydown', onKeyDownCallback);

        return () => {
            document.removeEventListener('keydown', onKeyDownCallback);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [builderState]);
    return <div>{children}</div>;
}
