import React, { BaseSyntheticEvent, useEffect } from 'react';

import { useRouter } from 'next/router';

import FormBuilderBlock from '@Components/FormBuilder/BuilderBlock/BuilderBlock';
import BuilderDragDropContext from '@Components/FormBuilder/DragDropContext';
import FormBuilderMenuBar from '@Components/FormBuilder/MenuBar';
import BuilderSpotlightDispatcher from '@Components/HOCs/BuilderSpotlightDispatcher';
import FormBuilderLeaveListener from '@Components/HOCs/FormBuilderLeaveListener';
import TextField from '@mui/material/TextField';
import { DragStart, DragUpdate, DropResult, OnDragEndResponder, OnDragStartResponder, OnDragUpdateResponder, ResponderProvided } from 'react-beautiful-dnd';
import { toast } from 'react-toastify';
import { v4 as uuidV4 } from 'uuid';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import builderConstants from '@app/constants/builder';
import useAsyncState from '@app/lib/hooks/use-async-state';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addField, deleteField, selectCreateForm, selectFormBuilderFields, setFields, setFormTitle, setIsFormDirty } from '@app/store/form-builder/slice';
import { IBuilderState, IFormFieldState } from '@app/store/form-builder/types';
import { initialIBuilderState } from '@app/store/forms/slice';
import { useAppAsyncDispatch, useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useCreateFormMutation, usePatchFormMutation } from '@app/store/workspaces/api';
import { reorder } from '@app/utils/arrayUtils';

export default function FormBuilder({ workspace, _nextI18Next, isEditMode = false }: { isEditMode?: boolean; workspace: WorkspaceDto; _nextI18Next: any }) {
    const dispatch = useAppDispatch();
    const asyncDispatch = useAppAsyncDispatch();

    const router = useRouter();

    const createForm: IBuilderState = useAppSelector(selectCreateForm);
    const formFields = useAppSelector(selectFormBuilderFields);

    const [postCreateForm] = useCreateFormMutation();
    const [patchForm] = usePatchFormMutation();

    const { openModal, closeModal } = useFullScreenModal();
    const basicModal = useModal();

    const [builderState, setBuilderState] = useAsyncState<IBuilderState>({
        id: '',
        title: '',
        description: '',
        fields: {},
        isFormDirty: false
    });

    const blocks: any = Object.values(formFields || {});
    const locale = _nextI18Next.initialLocale === 'en' ? '' : `${_nextI18Next.initialLocale}/`;

    const addBlockHandler = () => {
        const newBlock = {
            id: uuidV4(),
            type: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
            html: builderConstants.BuilderContentPlaceholder,
            placeholder: true,
            isTyping: false,
            imageUrl: ''
        };

        // Focus on the newly added block
        const addedBlockIndex = blocks.length;
        const blockElementId = `field-${addedBlockIndex}`;
        const blockElement = document.getElementById(blockElementId);
        if (blockElement) {
            blockElement.focus();
        }

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

    const onInsert = () => {
        basicModal.openModal('FORM_BUILDER_SPOTLIGHT_VIEW');
    };

    const onAddNewPage = () => {};

    const onAddFormLogo = () => {};

    const onAddFormCover = () => {};

    const onPreview = () => {
        openModal('FORM_BUILDER_PREVIEW', { form: createForm });
    };

    useEffect(() => {
        if (blocks.length === 0) {
            const newBlock = {
                id: uuidV4(),
                type: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
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

    const handleKeyDown = (event: React.KeyboardEvent, isTagSelectorOpen: boolean) => {
        event.preventDefault();
        // Add new block on Enter key press
        if (event.key === 'Enter') {
            addBlockHandler();
        }

        if (isTagSelectorOpen) return;

        // Move through the blocks on arrow key press
        if (event.key === 'ArrowUp') {
            const focusedBlockIndex = blocks.findIndex((block: any) => block.isFocused);
            const previousBlockIndex = focusedBlockIndex - 1;
            if (previousBlockIndex >= 0) {
                const previousBlockId = `field-${blocks[previousBlockIndex].id}`;
                const previousBlockElement = document.getElementById(previousBlockId);
                if (previousBlockElement) {
                    previousBlockElement.focus();
                }
            }
        }

        if (event.key === 'ArrowDown') {
            const focusedBlockIndex = blocks.findIndex((block: any) => block.isFocused);
            const nextBlockIndex = focusedBlockIndex + 1;
            if (nextBlockIndex < blocks.length) {
                const nextBlockId = `field-${blocks[nextBlockIndex].id}`;
                const nextBlockElement = document.getElementById(nextBlockId);
                if (nextBlockElement) {
                    nextBlockElement.focus();
                }
            }
        }
    };

    const onFormPublish = async () => {
        const apiCall = !isEditMode ? postCreateForm : patchForm;

        const redirectUrl = !isEditMode ? `/${workspace?.workspaceName}/dashboard` : `/${locale}${workspace?.workspaceName}/dashboard/forms/${createForm.id}`;
        const createUpdateText = !isEditMode ? 'creat' : 'updat';
        const publishRequest: any = {};
        publishRequest.title = createForm.title;
        publishRequest.description = createForm.description;
        let fields: any = Object.values(createForm.fields || {});
        fields = fields.map((field: IFormFieldState) => {
            if (field.properties?.choices) {
                return { ...field, properties: { ...field.properties, choices: Object.values(field.properties?.choices) } };
            }
            return field;
        });
        publishRequest.fields = fields;

        const apiObj: any = { workspaceId: workspace.id, body: publishRequest };
        if (isEditMode) apiObj['formId'] = createForm?.id;

        const response: any = await apiCall(apiObj);
        if (response?.data) {
            toast(`Form ${createUpdateText}ed!!`, { type: 'success' });
            asyncDispatch(setIsFormDirty(false)).then(async () => {
                await router.push(redirectUrl);
            });
        } else {
            toast(`Error ${createUpdateText}ing form`, { type: 'error' });
        }
    };

    return (
        <FormBuilderLeaveListener>
            <BuilderSpotlightDispatcher state={{ builderState, setBuilderState }}>
                <FormBuilderMenuBar onInsert={onInsert} onAddNewPage={onAddNewPage} onAddFormLogo={onAddFormLogo} onAddFormCover={onAddFormCover} onPreview={onPreview} onFormPublish={onFormPublish} />
                <div className="h-full w-full max-w-4xl mx-auto py-10">
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
                            onChange={async (e: BaseSyntheticEvent) => {
                                asyncDispatch(setIsFormDirty(true));
                                dispatch(setFormTitle(e.target.value));
                            }}
                        />
                    </div>
                    <BuilderDragDropContext
                        Component={FormBuilderBlock}
                        componentAttrs={{
                            fields: formFields,
                            onKeyDown: handleKeyDown,
                            addBlock: addBlockHandler,
                            duplicateBlock: duplicateBlockHandler,
                            deleteBlock: deleteBlockHandler,
                            updateBlock: updateBlockHandler
                        }}
                        droppableId="form-builder"
                        droppableItems={blocks}
                        droppableClassName="py-10"
                        onDragStartHandlerCallback={onDragStartHandler}
                        onDragUpdateHandlerCallback={onDragUpdateHandler}
                        onDragEndHandlerCallback={onDragEndHandler}
                    />
                </div>
            </BuilderSpotlightDispatcher>
        </FormBuilderLeaveListener>
    );
}
