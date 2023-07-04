import React, { BaseSyntheticEvent, useEffect, useState } from 'react';

import FormBuilderBlock from '@Components/FormBuilder/BuilderBlock';
import { StrictModeDroppable } from '@Components/FormBuilder/StrictModeDroppable';
import FormBuilderHotkeysHookListener from '@Components/HOCs/FormBuilderHotkeysHookListener';
import TextField from '@mui/material/TextField';
import { DragDropContext, DragStart, DragUpdate, DropResult, DroppableProvided, DroppableStateSnapshot, OnDragEndResponder, OnDragStartResponder, OnDragUpdateResponder, ResponderProvided } from 'react-beautiful-dnd';
import { HotkeysProvider } from 'react-hotkeys-hook';
import { v4 as uuidV4 } from 'uuid';

import builderConstants from '@app/constants/builder';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addField, deleteField, selectFormBuilderFields, setFields } from '@app/store/form-builder/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

interface IFormBuilderProps {
    formId: string;
    formData: any;
}

export default function FormBuilder({ formId, formData }: IFormBuilderProps) {
    const dispatch = useAppDispatch();

    const [formTitle, setFormTitle] = useState(formData?.title ?? '');

    const formFields = useAppSelector(selectFormBuilderFields);

    const blocks: any = Object.values(formFields);

    const reorder = (list: Array<any>, startIndex: number, endIndex: number) => {
        const result = Array.from(list);
        const [removed] = result.splice(startIndex - 1, 1);
        result.splice(endIndex - 1, 0, removed);
        return result;
    };

    const addBlockHandler = (block: any) => {
        const newBlock = {
            id: uuidV4(),
            tag: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
            html: builderConstants.BuilderContentPlaceholder,
            placeholder: true,
            isTyping: false,
            imageUrl: ''
            // content: null,
            // contentPlaceholder: builderConstants.BuilderContentPlaceholder,
            // properties: {},
            // validations: {},
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

    useEffect(() => {
        if (blocks.length === 0) {
            const newBlock = {
                id: uuidV4(),
                tag: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
                html: builderConstants.BuilderContentPlaceholder,
                placeholder: true,
                isTyping: false,
                imageUrl: ''
                // content: null,
                // contentPlaceholder: builderConstants.BuilderContentPlaceholder,
                // properties: {},
                // validations: {},
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

    return (
        <div className="min-h-calc-68 w-full max-w-4xl mx-auto py-10">
            <div className="px-5 md:px-[89px]">
                <TextField
                    required
                    fullWidth
                    margin="none"
                    value={formTitle}
                    placeholder="Form title"
                    variant="standard"
                    inputMode="text"
                    inputProps={{
                        style: {
                            padding: '0 0 8px 0',
                            fontSize: 30,
                            fontWeight: 600,
                            content: 'none',
                            letterSpacing: 1
                        }
                    }}
                    InputProps={{ sx: { ':before': { content: 'none' } } }}
                    size="medium"
                    onChange={(e: BaseSyntheticEvent) => {
                        setFormTitle(e.target.value);
                    }}
                />
            </div>
            <HotkeysProvider initiallyActiveScopes={['builder']}>
                <FormBuilderHotkeysHookListener scopes="builder">
                    <DragDropContext onDragStart={onDragStartHandler} onDragUpdate={onDragUpdateHandler} onDragEnd={onDragEndHandler}>
                        <StrictModeDroppable droppableId="droppable">
                            {(provided: DroppableProvided, snapshot: DroppableStateSnapshot) => (
                                <div className={`flex flex-col py-10 gap-2 transition-all duration-200 ease-in ${snapshot.isDraggingOver ? 'bg-black-100 bg-opacity-30 rounded' : 'bg-white'}`} {...provided.droppableProps} ref={provided.innerRef}>
                                    {blocks.map((block: any) => {
                                        const position = blocks.map((b: any) => b.id).indexOf(block.id) + 1;
                                        return (
                                            <FormBuilderBlock
                                                key={block.id}
                                                field={block}
                                                position={position}
                                                dispatch={dispatch}
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
    );
}
