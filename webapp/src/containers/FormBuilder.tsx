import React, { FormEvent, useEffect } from 'react';

import { useRouter } from 'next/router';

import NewFormBuilderBlock from '@Components/FormBuilder/BuilderBlock';
import FormBuilderBlock from '@Components/FormBuilder/BuilderBlock/BuilderBlock';
import BuilderTips from '@Components/FormBuilder/BuilderTips';
import CustomContentEditable from '@Components/FormBuilder/ContentEditable/CustomContentEditable';
import BuilderDragDropContext from '@Components/FormBuilder/DragDropContext';
import FormBuilderMenuBar from '@Components/FormBuilder/MenuBar';
import { DragStart, DragUpdate, DropResult, OnDragEndResponder, OnDragStartResponder, OnDragUpdateResponder, ResponderProvided } from 'react-beautiful-dnd';
import { toast } from 'react-toastify';
import { v4 as uuidV4 } from 'uuid';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import builderConstants from '@app/constants/builder';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setBuilderState } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { deleteField, selectCreateForm, selectFormBuilderFields, setFields, updateField } from '@app/store/form-builder/slice';
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

    const createForm: IBuilderState = useAppSelector(selectCreateForm);
    const formFields = builderState.fields;

    const [postCreateForm] = useCreateFormMutation();
    const [patchForm] = usePatchFormMutation();

    const fullScreenModal = useFullScreenModal();
    const modal = useModal();

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

        dispatch(updateField(newBlock));
    };

    const duplicateBlockHandler = () => {};

    const deleteBlockHandler = (id: string) => {
        if (blocks.length > 1) {
            dispatch(deleteField(id));
        }
    };

    const updateBlockHandler = (block: any) => {
        dispatch(updateField(block));
    };

    const onInsert = () => {
        modal.openModal('FORM_BUILDER_ADD_FIELD_VIEW');
    };

    const onAddNewPage = () => {};

    const onAddFormLogo = () => {};

    const onAddFormCover = () => {};

    const onPreview = () => {
        fullScreenModal.openModal('FORM_BUILDER_PREVIEW', { form: createForm });
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
            dispatch(updateField(newBlock));
        }
    }, []);

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
            asyncDispatch(setBuilderState({ isFormDirty: false })).then(async () => {
                await router.push(redirectUrl);
            });
        } else {
            toast(`Error ${createUpdateText}ing form`, { type: 'error' });
        }
    };

    return (
        <>
            <FormBuilderMenuBar onInsert={onInsert} onAddNewPage={onAddNewPage} onAddFormLogo={onAddFormLogo} onAddFormCover={onAddFormCover} onPreview={onPreview} onFormPublish={onFormPublish} />
            <div className="h-full w-full max-w-4xl mx-auto py-10">
                <div className="flex flex-col gap-4 px-5 md:px-[89px]">
                    {builderTitleAndDescriptionList.map((b: IBuilderTitleAndDescriptionObj, idx: number) => (
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
                                // @ts-ignore
                                const value = b.key === 'title' ? event.currentTarget.innerText : event.target.value;
                                dispatch(setBuilderState({ isFormDirty: true, [b.key]: value }));
                            }}
                            onKeyUpCallback={(event: React.KeyboardEvent<HTMLElement>) => {
                                if ((event.key === 'Enter' && !event.shiftKey) || event.key === 'ArrowDown') {
                                    // TODO: add support for activeFieldIndex increase if there are no elements
                                    // TODO: add support for delete key and backspace key
                                    event.preventDefault();
                                    dispatch(setBuilderState({ activeFieldIndex: idx + 1 }));
                                }
                                if ((event.key === 'ArrowUp' || (event.shiftKey && event.key === 'Tab')) && idx > 0) {
                                    dispatch(setBuilderState({ activeFieldIndex: idx - 1 }));
                                }
                            }}
                            onFocusCallback={(event: React.FocusEvent<HTMLElement>) => {
                                dispatch(setBuilderState({ activeFieldIndex: b.position }));
                            }}
                        />
                    ))}
                </div>
                <NewFormBuilderBlock positionOffset={2} />
                {/* <BuilderDragDropContext
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
                /> */}
                <BuilderTips />
            </div>
        </>
    );
}
