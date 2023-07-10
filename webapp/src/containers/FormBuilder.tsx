import React, { BaseSyntheticEvent, useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import _ from 'lodash';

import FormBuilderBlock from '@Components/FormBuilder/BuilderBlock';
import NewFormBuilderBlock from '@Components/FormBuilder/BuilderBlock/BuilderBlock';
import FormBuilderMenuBar from '@Components/FormBuilder/MenuBar';
import { StrictModeDroppable } from '@Components/FormBuilder/StrictModeDroppable';
import FormBuilderHotkeysHookListener from '@Components/HOCs/FormBuilderHotkeysHookListener';
import TextField from '@mui/material/TextField';
import { DragDropContext, DragStart, DragUpdate, DropResult, DroppableProvided, DroppableStateSnapshot, OnDragEndResponder, OnDragStartResponder, OnDragUpdateResponder, ResponderProvided } from 'react-beautiful-dnd';
import { HotkeysProvider } from 'react-hotkeys-hook';
import { toast } from 'react-toastify';
import { v4 as uuidV4 } from 'uuid';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import builderConstants from '@app/constants/builder';
import useAsyncState from '@app/lib/hooks/use-async-state';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addField, deleteField, selectCreateForm, selectFormBuilderFields, setFields, setFormTitle } from '@app/store/form-builder/slice';
import { FormFieldState, FormState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useCreateFormMutation, usePatchFormMutation } from '@app/store/workspaces/api';
import { reorder } from '@app/utils/arrayUtils';

export default function FormBuilder({ workspace, _nextI18Next, isEditMode = false }: { isEditMode?: boolean; workspace: WorkspaceDto; _nextI18Next: any }) {
    const dispatch = useAppDispatch();
    const router = useRouter();
    const createForm: FormState = useAppSelector(selectCreateForm);

    const [postCreateForm] = useCreateFormMutation();
    const [patchForm] = usePatchFormMutation();
    const [isFormDirty, setIsFormDirty] = useAsyncState(false);

    const { openModal, closeModal } = useFullScreenModal();

    const formFields = useAppSelector(selectFormBuilderFields);

    const blocks: any = Object.values(formFields);
    const locale = _nextI18Next.initialLocale === 'en' ? '' : `${_nextI18Next.initialLocale}/`;

    const addBlockHandler = (block: any) => {
        const newBlock = {
            id: uuidV4(),
            tag: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
            html: builderConstants.BuilderContentPlaceholder,
            placeholder: true,
            isTyping: false,
            imageUrl: ''
        };
        dispatch(addField(newBlock));
    };

    const duplicateBlockHandler = () => {};

    const deleteBlockHandler = (id: string) => {
        if (blocks.length > 1) {
            dispatch(deleteField(id));
        }
    };

    const updateBlockHandler = (block: any) => {
        dispatch(addField(block));
    };

    const onInsert = () => {};

    const onAddNewPage = () => {};

    const onAddFormLogo = () => {};

    const onAddFormCover = () => {};

    const onPreview = () => {
        openModal('FORM_BUILDER_PREVIEW');
    };

    useEffect(() => {
        const handleBeforeUnload = (event: any) => {
            if (isFormDirty) {
                event.preventDefault();
                event.returnValue = ''; // This empty string will prompt the browser to show a confirmation dialog
            }
        };

        const handleBeforePopState = (state: any) => {
            if (isFormDirty && !window.confirm('Are you sure you want to leave? Your changes will not be saved.')) {
                router.events.emit('routeChangeError', state);
                throw "Abort route change by user's confirmation."; // Prevent navigation
            }
            return true; // Allow navigation
        };

        const handleError = (state: any) => {
            // Handle the route change error
            // You can customize this function to perform any necessary actions
            return null;
        };

        window.addEventListener('beforeunload', handleBeforeUnload);
        router.events.on('routeChangeStart', handleBeforePopState);
        router.events.on('routeChangeError', handleError);

        return () => {
            window.removeEventListener('beforeunload', handleBeforeUnload);
            router.events.off('routeChangeStart', handleBeforePopState);
            router.events.off('routeChangeError', handleError);
        };
    }, [isFormDirty, router]);

    useEffect(() => {
        if (blocks.length === 0) {
            const newBlock = {
                id: uuidV4(),
                tag: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
                html: builderConstants.BuilderContentPlaceholder,
                placeholder: true,
                isTyping: false,
                imageUrl: ''
            };
            dispatch(addField(newBlock));
        }
    }, [blocks]);

    const onDragStartHandler: OnDragStartResponder = (start: DragStart, provided: ResponderProvided) => {};

    const onDragUpdateHandler: OnDragUpdateResponder = (update: DragUpdate, provided: ResponderProvided) => {};

    const onDragEndHandler: OnDragEndResponder = (result: DropResult, provided: ResponderProvided) => {
        if (!result.destination) {
            return;
        }
        const items = reorder(blocks, result.source.index, result.destination.index);
        dispatch(setFields(items));
    };

    const onFormPublish = async () => {
        const apiCall = !isEditMode ? postCreateForm : patchForm;

        const redirectUrl = !isEditMode ? `/${workspace?.workspaceName}/dashboard` : `/${locale}${workspace?.workspaceName}/dashboard/forms/${createForm.formId}`;
        const createUpdateText = !isEditMode ? 'creat' : 'updat';
        const publishRequest: any = {};
        publishRequest.title = createForm.title;
        publishRequest.description = createForm.description;
        let fields: any = Object.values(createForm.fields);
        fields = fields.map((field: FormFieldState) => {
            if (field.properties?.choices) {
                return { ...field, properties: { ...field.properties, choices: Object.values(field.properties?.choices) } };
            }
            return field;
        });
        publishRequest.fields = fields;

        const apiObj: any = { workspaceId: workspace.id, body: publishRequest };
        if (isEditMode) apiObj['formId'] = createForm.formId;

        const response: any = await apiCall(apiObj);
        if (response?.data) {
            toast(`Form ${createUpdateText}ed!!`, { type: 'success' });
            setIsFormDirty(false).then(async () => {
                await router.push(redirectUrl);
            });
        } else {
            toast(`Error ${createUpdateText}ing form`, { type: 'error' });
        }
    };

    return (
        <>
            <FormBuilderMenuBar onInsert={onInsert} onAddNewPage={onAddNewPage} onAddFormLogo={onAddFormLogo} onAddFormCover={onAddFormCover} onPreview={onPreview} onFormPublish={onFormPublish} />
            <div className="min-h-calc-68 w-full max-w-4xl mx-auto py-10">
                <div className="px-5 md:px-[89px]">
                    <TextField
                        required
                        fullWidth
                        margin="none"
                        value={createForm?.title || ''}
                        placeholder="Form title"
                        variant="standard"
                        inputMode="text"
                        inputProps={{
                            style: {
                                padding: '0 0 8px 0',
                                fontSize: 36,
                                fontWeight: 700,
                                content: 'none',
                                letterSpacing: 1
                            }
                        }}
                        InputProps={{ sx: { ':before': { content: 'none' } } }}
                        size="medium"
                        onChange={(e: BaseSyntheticEvent) => {
                            setIsFormDirty(true);
                            dispatch(setFormTitle(e.target.value));
                        }}
                    />
                </div>
                <HotkeysProvider initiallyActiveScopes={['builder']}>
                    <FormBuilderHotkeysHookListener scopes="builder" addBlock={addBlockHandler}>
                        <DragDropContext onDragStart={onDragStartHandler} onDragUpdate={onDragUpdateHandler} onDragEnd={onDragEndHandler}>
                            <StrictModeDroppable droppableId="droppable">
                                {(provided: DroppableProvided, snapshot: DroppableStateSnapshot) => (
                                    <div className={`flex flex-col py-10 gap-2 transition-all duration-200 ease-in ${snapshot.isDraggingOver ? 'bg-black-100 bg-opacity-30 rounded' : 'bg-white'}`} {...provided.droppableProps} ref={provided.innerRef}>
                                        {blocks.map((block: any, index: number) => {
                                            return (
                                                <NewFormBuilderBlock
                                                    fields={formFields}
                                                    key={block.id}
                                                    field={block}
                                                    position={index}
                                                    dispatch={dispatch}
                                                    setIsFormDirty={setIsFormDirty}
                                                    addBlock={addBlockHandler}
                                                    duplicateBlock={duplicateBlockHandler}
                                                    deleteBlock={deleteBlockHandler}
                                                    updateBlock={updateBlockHandler}
                                                />
                                            );
                                        })}
                                        {provided.placeholder}
                                    </div>
                                )}
                            </StrictModeDroppable>
                        </DragDropContext>
                    </FormBuilderHotkeysHookListener>
                </HotkeysProvider>
            </div>
        </>
    );
}
