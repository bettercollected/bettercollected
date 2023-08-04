import React, { useCallback, useEffect, useRef } from 'react';

import { throttle } from 'lodash';

import { batch } from 'react-redux';
import { toast } from 'react-toastify';
import { v4 } from 'uuid';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import useFormBuilderState from '@app/containers/form-builder/context';
import eventBus from '@app/lib/event-bus';
import { FormBuilderEventBusType } from '@app/models/enums/formBuilder';
import { addDuplicateField, resetBuilderMenuState, setActiveChoice, setAddNewChoice, setAddNewField, setBuilderState, setDeleteChoice, setDeleteField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IBuilderState, IFormFieldState } from '@app/store/form-builder/types';
import { useAppAsyncDispatch, useAppDispatch, useAppSelector } from '@app/store/hooks';
import { createNewField, isMultipleChoice } from '@app/utils/formBuilderBlockUtils';

export default function FormBuilderKeyDownListerner({ children }: React.PropsWithChildren) {
    const dispatch = useAppDispatch();
    const asyncDispatch = useAppAsyncDispatch();
    const builderDragDropRef = useRef<HTMLDivElement | null>(null);
    const onKeyDownCallbackRef = useRef<any>(null);
    const { backspaceCount, setBackspaceCount } = useFormBuilderState();

    const builderState: IBuilderState = useAppSelector(selectBuilderState);
    const fullScreenModal = useFullScreenModal();
    const modal = useModal();

    const onInsert = () => {
        asyncDispatch(resetBuilderMenuState()).then(() => {
            modal.openModal('FORM_BUILDER_ADD_FIELD_VIEW');
        });
    };

    const onKeyDownCallback = useCallback(
        (event: KeyboardEvent) => {
            batch(async () => {
                const fieldId = builderState.activeFieldId;
                const formField: IFormFieldState | undefined = builderState.fields[fieldId];
                console.log(event.key);
                if (event.key === 'Escape') {
                    dispatch(resetBuilderMenuState());
                }

                if (builderState.menus?.commands?.isOpen || fullScreenModal.isOpen || modal.isOpen || builderState.menus?.spotlightField?.isOpen) {
                    // event.preventDefault();
                    // event.stopPropagation();
                    return;
                }

                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    event.stopPropagation();
                    if (isMultipleChoice(formField?.type) && builderState.activeFieldIndex >= -1) {
                        //@ts-ignore
                        if ((formField.properties?.choices[formField.properties.activeChoiceId].value || '') !== '') {
                            dispatch(setAddNewChoice());
                        } else {
                            const choices = { ...formField.properties?.choices };
                            //@ts-ignore
                            dispatch(setDeleteChoice(formField.properties.activeChoiceId));
                            if (Object.values(choices).length - 1 === 0) dispatch(setDeleteField(formField.id));
                            dispatch(setAddNewField(createNewField(builderState.activeFieldIndex)));
                            dispatch(
                                setBuilderState({
                                    isFormDirty: true,
                                    activeFieldIndex: builderState.activeFieldIndex + (Object.values(choices).length - 1 === 0 ? 0 : 1)
                                })
                            );
                        }
                    } else if (builderState.activeFieldIndex >= -1) {
                        dispatch(setAddNewField(createNewField(builderState.activeFieldIndex)));
                        dispatch(
                            setBuilderState({
                                isFormDirty: true,
                                activeFieldIndex: builderState.activeFieldIndex + 1
                            })
                        );
                    }
                }

                if (event.key === 'Tab' || (event.shiftKey && event.key === 'Tab')) event.preventDefault();
                // Only for multiple choice
                if (event.key === 'ArrowDown' && isMultipleChoice(formField?.type)) {
                    //@ts-ignore
                    if (formField.properties?.activeChoiceIndex < Object.values(formField.properties?.choices).length - 1) {
                        dispatch(setActiveChoice({ position: (formField.properties?.activeChoiceIndex ?? 0) + 1 }));
                    }
                }
                if (event.key === 'ArrowUp' && isMultipleChoice(formField?.type)) {
                    //@ts-ignore
                    if (formField.properties?.activeChoiceIndex > 0) {
                        dispatch(setActiveChoice({ position: (formField.properties?.activeChoiceIndex ?? 0) - 1 }));
                    }
                }
                if (
                    !event.ctrlKey &&
                    !event.metaKey &&
                    (event.key === 'ArrowDown' || (event.key === 'Enter' && builderState.activeFieldIndex < -1)) &&
                    builderState.activeFieldIndex < Object.keys(builderState.fields).length - 1 &&
                    (!isMultipleChoice(formField?.type) || formField?.properties?.activeChoiceIndex === Object.values(formField?.properties?.choices ?? {}).length - 1)
                ) {
                    dispatch(setBuilderState({ activeFieldIndex: builderState.activeFieldIndex + 1 }));
                }
                if (!event.ctrlKey && !event.metaKey && event.key === 'ArrowUp' && builderState.activeFieldIndex > -2 && (!isMultipleChoice(formField?.type) || (formField.properties?.activeChoiceIndex ?? 0) === 0)) {
                    dispatch(setBuilderState({ activeFieldIndex: builderState.activeFieldIndex - 1 }));
                }
                if (event.code === 'Slash' && builderState.activeFieldIndex >= 0 && !event.shiftKey) {
                    const viewportHeight = window.innerHeight;
                    const bottomPosition = builderDragDropRef.current?.getBoundingClientRect().bottom ?? 0;
                    console.log({
                        viewportHeight,
                        bottomPosition,
                        position: bottomPosition + 300 > viewportHeight ? 'up' : 'down'
                    });
                    // 300 is the height of the FormBuilderTagSelector
                    dispatch(
                        setBuilderState({
                            isFormDirty: true,
                            menus: {
                                ...builderState.menus,
                                commands: {
                                    isOpen: true,
                                    atFieldUuid: Object.keys(builderState.fields).at(builderState.activeFieldIndex) ?? '',
                                    position: bottomPosition + 300 > viewportHeight ? 'up' : 'down'
                                }
                            }
                        })
                    );
                }
                if (event.key === 'Backspace' && (!event.metaKey || !event.ctrlKey) && builderState.activeFieldIndex >= 0) {
                    console.log({ 'backspace count': backspaceCount });
                    console.log('backspace pressed');
                    // TODO: Add support for other input types or form field type as well
                    if (!formField?.value && backspaceCount === 1) {
                        asyncDispatch(setDeleteField(fieldId)).then(() => setBackspaceCount(0));
                        dispatch(setBuilderState({ activeFieldIndex: builderState.activeFieldIndex - 1 }));
                    } else {
                        setBackspaceCount(1);
                    }
                    dispatch(
                        setBuilderState({
                            isFormDirty: true,
                            menus: { ...builderState.menus, commands: { isOpen: false, atFieldUuid: '', position: 'down' } }
                        })
                    );
                }

                if (((event.key === 'Delete' && event.ctrlKey) || (event.key === 'Backspace' && event.metaKey)) && fieldId) {
                    event.preventDefault();
                    event.stopPropagation();

                    if (builderState.activeFieldIndex < 0) {
                        toast("Can't delete the form title and description", { type: 'warning' });
                    } else dispatch(setDeleteField(fieldId));
                    dispatch(
                        setBuilderState({
                            isFormDirty: true,
                            activeFieldIndex: builderState.activeFieldIndex > 0 ? builderState.activeFieldIndex - 1 : 0
                        })
                    );
                }
                if ((event.key === 'D' || event.key === 'd') && !event.shiftKey && (event.ctrlKey || event.metaKey) && fieldId) {
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
                }
                if ((event.key === 'I' || event.key === 'i') && !event.shiftKey && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();
                    event.stopPropagation();
                    onInsert();
                }
                if ((event.key === 'S' || event.key === 's') && !event.shiftKey && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();
                    event.stopPropagation();
                    eventBus.emit(FormBuilderEventBusType.Save);
                }
                if ((event.key === 'P' || event.key === 'p') && !event.shiftKey && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();
                    event.stopPropagation();
                    eventBus.emit(FormBuilderEventBusType.Publish);
                }
            });
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [builderState, backspaceCount]
    );

    useEffect(() => {
        onKeyDownCallbackRef.current = throttle(onKeyDownCallback, 100);

        document.addEventListener('keydown', onKeyDownCallback);

        return () => {
            document.removeEventListener('keydown', onKeyDownCallback);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [builderState, onKeyDownCallback]);

    return <div>{children}</div>;
}
