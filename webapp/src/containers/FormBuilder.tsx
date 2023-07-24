import React, { FormEvent, useCallback, useEffect, useRef } from 'react';

import { useRouter } from 'next/router';

import FormBuilderBlock from '@Components/FormBuilder/BuilderBlock';
import BuilderTips from '@Components/FormBuilder/BuilderTips';
import CustomContentEditable from '@Components/FormBuilder/ContentEditable/CustomContentEditable';
import BuilderDragDropContext from '@Components/FormBuilder/DragDropContext';
import FormBuilderMenuBar from '@Components/FormBuilder/MenuBar';
import { DragStart, DragUpdate, DropResult, ResponderProvided } from 'react-beautiful-dnd';
import { batch } from 'react-redux';
import { toast } from 'react-toastify';
import { v4 } from 'uuid';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addDuplicateField, setAddNewField, setBuilderState, setDeleteField, setFields } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IBuilderState, IBuilderTitleAndDescriptionObj, IFormFieldState } from '@app/store/form-builder/types';
import { builderTitleAndDescriptionList } from '@app/store/form-builder/utils';
import { useAppAsyncDispatch, useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useCreateFormMutation, usePatchFormMutation } from '@app/store/workspaces/api';
import { reorder } from '@app/utils/arrayUtils';

export default function FormBuilder({ workspace, _nextI18Next, isEditMode = false }: { isEditMode?: boolean; workspace: WorkspaceDto; _nextI18Next: any }) {
    const dispatch = useAppDispatch();
    const asyncDispatch = useAppAsyncDispatch();

    const router = useRouter();

    const builderState: IBuilderState = useAppSelector(selectBuilderState);
    const onKeyUpCallbackRef = useRef<any>(null);
    const onBlurCallbackRef = useRef<any>(null);

    const [postCreateForm] = useCreateFormMutation();
    const [patchForm] = usePatchFormMutation();

    const fullScreenModal = useFullScreenModal();
    const modal = useModal();

    const locale = _nextI18Next.initialLocale === 'en' ? '' : `${_nextI18Next.initialLocale}/`;

    const onInsert = () => {
        modal.openModal('FORM_BUILDER_ADD_FIELD_VIEW');
    };

    const onAddNewPage = () => {};

    const onAddFormLogo = () => {};

    const onAddFormCover = () => {};

    const onPreview = () => {
        fullScreenModal.openModal('FORM_BUILDER_PREVIEW');
    };

    const onFormPublish = async () => {
        const apiCall = !isEditMode ? postCreateForm : patchForm;

        const redirectUrl = !isEditMode ? `/${workspace?.workspaceName}/dashboard` : `/${locale}${workspace?.workspaceName}/dashboard/forms/${builderState.id}`;
        const createUpdateText = !isEditMode ? 'creat' : 'updat';
        const publishRequest: any = {};
        publishRequest.title = builderState.title;
        publishRequest.description = builderState.description;
        let fields: any = Object.values(builderState.fields || {});
        fields = fields.map((field: IFormFieldState) => {
            if (field.properties?.choices) {
                return { ...field, properties: { ...field.properties, choices: Object.values(field.properties?.choices) } };
            }
            return field;
        });
        publishRequest.fields = fields;

        const apiObj: any = { workspaceId: workspace.id, body: publishRequest };
        if (isEditMode) apiObj['formId'] = builderState?.id;

        const response: any = await apiCall(apiObj);
        if (response?.data) {
            toast(`Form ${createUpdateText}ed!!`, { type: 'success' });
            asyncDispatch(setBuilderState({ isFormDirty: false })).then(async () => {
                await router.push(redirectUrl);
            });
        } else {
            toast(`Error ${createUpdateText}ing form`, { type: 'error' });
        }
    };

    const throttle = (func: Function, delay: number) => {
        let timeoutId: any;
        return (...args: any[]) => {
            if (!timeoutId) {
                timeoutId = setTimeout(() => {
                    // @ts-ignore
                    func.apply(this, args);
                    timeoutId = null;
                }, delay);
            }
        };
    };

    const onKeyUpCallback = useCallback(
        (event: KeyboardEvent) => {
            batch(() => {
                if (event.key === 'Escape') {
                    event.preventDefault();
                    dispatch(
                        setBuilderState({
                            isFormDirty: true,
                            menus: { ...builderState.menus, commands: { isOpen: false, atFieldUuid: '' } }
                        })
                    );
                }
                console.log(builderState.menus?.commands?.isOpen || builderState.menus?.spotlightField?.isOpen);
                if (builderState.menus?.commands?.isOpen || builderState.menus?.spotlightField?.isOpen) return;

                if (event.key === 'Enter' && !event.shiftKey && builderState.activeFieldIndex >= -1) {
                    const newField: IFormFieldState = {
                        id: v4(),
                        type: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
                        isCommandMenuOpen: false,
                        position: builderState.activeFieldIndex
                    };
                    dispatch(setAddNewField(newField));
                    dispatch(setBuilderState({ isFormDirty: true, activeFieldIndex: builderState.activeFieldIndex + 1 }));
                }
                if ((event.key === 'ArrowDown' || event.key === 'Tab' || (event.key === 'Enter' && builderState.activeFieldIndex < -1)) && builderState.activeFieldIndex < Object.keys(builderState.fields).length - 1) {
                    // TODO: add support for activeFieldIndex increase if there are no elements
                    // TODO: add support for delete key and backspace key
                    event.preventDefault();

                    dispatch(setBuilderState({ activeFieldIndex: builderState.activeFieldIndex + 1 }));
                }
                if ((event.key === 'ArrowUp' || (event.shiftKey && event.key === 'Tab')) && builderState.activeFieldIndex > -2) {
                    dispatch(setBuilderState({ activeFieldIndex: builderState.activeFieldIndex - 1 }));
                }
                if (event.code === 'Slash' && builderState.activeFieldIndex >= 0) {
                    dispatch(
                        setBuilderState({
                            isFormDirty: true,
                            menus: {
                                ...builderState.menus,
                                commands: {
                                    isOpen: true,
                                    atFieldUuid: Object.keys(builderState.fields).at(builderState.activeFieldIndex) ?? ''
                                }
                            }
                        })
                    );
                }
                if (event.key === 'Backspace' && builderState.activeFieldIndex >= 0) {
                    const fieldId = Object.keys(builderState.fields).at(builderState.activeFieldIndex) ?? '';
                    // TODO: remove the label and if clicked the backspace on empty label delete the field
                    // if (fieldId) dispatch(setDeleteField(fieldId));
                    dispatch(setBuilderState({ isFormDirty: true }));
                }
                if (event.key === 'Delete' && event.altKey) {
                    // TODO: fix delete proxy issue
                    event.preventDefault();

                    const fieldId = Object.keys(builderState.fields).at(builderState.activeFieldIndex) ?? '';
                    if (fieldId) dispatch(setDeleteField(fieldId));
                    dispatch(
                        setBuilderState({
                            isFormDirty: true,
                            activeFieldIndex: builderState.activeFieldIndex > 0 ? builderState.activeFieldIndex - 1 : 0
                        })
                    );
                }
                if (event.code === 'KeyD' && event.shiftKey && event.altKey) {
                    event.preventDefault();
                    const fieldId = Object.keys(builderState.fields).at(builderState.activeFieldIndex) ?? '';
                    if (fieldId) {
                        const formField = builderState.fields[fieldId];
                        const newField: IFormFieldState = { ...formField };
                        newField.id = v4();
                        newField.position = builderState.activeFieldIndex + 1;
                        dispatch(addDuplicateField(newField));
                    }
                    dispatch(setBuilderState({ isFormDirty: true }));
                }
            });
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [builderState]
    );

    const onBlurCallback = useCallback(
        (event: FocusEvent) => {
            event.preventDefault();
            dispatch(setBuilderState({ menus: { ...builderState.menus, commands: { isOpen: false, atFieldUuid: '' } } }));
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [builderState]
    );

    useEffect(() => {
        if (Object.values(builderState.fields).length === 0) {
            const newField: IFormFieldState = {
                id: v4(),
                type: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
                isCommandMenuOpen: false,
                position: Object.values(builderState.fields).length === 0 ? 0 : Object.values(builderState.fields).length
            };
            dispatch(setAddNewField(newField));
            (async () => await asyncDispatch(setAddNewField(newField)))();
        }

        onKeyUpCallbackRef.current = throttle(onKeyUpCallback, 100);

        onBlurCallbackRef.current = onBlurCallback;

        document.addEventListener('keyup', onKeyUpCallback);
        document.addEventListener('blur', onBlurCallback);

        return () => {
            document.removeEventListener('keyup', onKeyUpCallback);
            document.removeEventListener('blur', onBlurCallback);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [builderState, onKeyUpCallback, onBlurCallback]);

    return (
        <>
            <FormBuilderMenuBar onInsert={onInsert} onAddNewPage={onAddNewPage} onAddFormLogo={onAddFormLogo} onAddFormCover={onAddFormCover} onPreview={onPreview} onFormPublish={onFormPublish} />
            <div className="h-full w-full max-w-4xl mx-auto py-10">
                <div className="flex flex-col gap-4 px-5 md:px-[89px]">
                    {builderTitleAndDescriptionList.map((b: IBuilderTitleAndDescriptionObj) => (
                        <CustomContentEditable
                            key={b.id}
                            id={b.id}
                            tagName={b.tagName}
                            type={b.type}
                            value={builderState[b.key]}
                            position={b.position}
                            activeFieldIndex={builderState.activeFieldIndex}
                            placeholder={b.placeholder}
                            className={b.className}
                            onChangeCallback={(event: FormEvent<HTMLElement>) => {
                                dispatch(setBuilderState({ isFormDirty: true, [b.key]: event.currentTarget.innerText }));
                            }}
                            onFocusCallback={(event: React.FocusEvent<HTMLElement>) => {
                                dispatch(setBuilderState({ activeFieldIndex: b.position }));
                            }}
                        />
                    ))}
                </div>
                <BuilderDragDropContext
                    Component={FormBuilderBlock}
                    componentAttrs={{}}
                    droppableId="form-builder"
                    droppableItems={Object.values(builderState.fields || {})}
                    droppableClassName="py-10"
                    onDragStartHandlerCallback={(start: DragStart, provided: ResponderProvided) => {}}
                    onDragUpdateHandlerCallback={(update: DragUpdate, provided: ResponderProvided) => {}}
                    onDragEndHandlerCallback={(result: DropResult, provided: ResponderProvided) => {
                        if (!result.destination?.index) {
                            return;
                        }
                        const items: Array<IFormFieldState> = reorder(Object.values(builderState.fields), result.source.index, result.destination.index);
                        batch(() => {
                            dispatch(setFields(items));
                            dispatch(setBuilderState({ activeFieldIndex: result.destination?.index ?? builderState.activeFieldIndex }));
                        });
                    }}
                />
                <BuilderTips />
            </div>
        </>
    );
}
