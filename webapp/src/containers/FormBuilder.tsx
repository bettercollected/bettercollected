import React, { useEffect, useState } from 'react';

import DragHandleIcon from '@Components/Common/Icons/DragHandle';
import FormBuilderBlock from '@Components/FormBuilder/BuilderBlock';
import { StrictModeDroppable } from '@Components/FormBuilder/StrictModeDroppable';
import FormBuilderDescriptionField from '@Components/FormBuilder/TitleAndDescription/FormBuilderDescriptionField';
import FormBuilderTitleInput from '@Components/FormBuilder/TitleAndDescription/FormBuilderTitleInput';
import FormBuilderHotkeysHookListener from '@Components/HOCs/FormBuilderHotkeysHookListener';
import {
    DragDropContext,
    DragStart,
    DragUpdate,
    Draggable,
    DraggableProvided,
    DraggableStateSnapshot,
    DropResult,
    DroppableProvided,
    DroppableStateSnapshot,
    OnDragEndResponder,
    OnDragStartResponder,
    OnDragUpdateResponder,
    ResponderProvided
} from 'react-beautiful-dnd';
import { HotkeysProvider } from 'react-hotkeys-hook';
import { v4 as uuidv4 } from 'uuid';

import builderConstants from '@app/constants/builder';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addField, deleteField, selectFormBuilderFields, setFields } from '@app/store/form-builder/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

// TODO: this is for test
const Column = ({ column, tasks }: any) => {
    return (
        <div className="my-2 flex flex-col gap-4">
            <h3 className="sh3 cursor-pointer">{column.title}</h3>
            <StrictModeDroppable droppableId={column.id}>
                {(provided: DroppableProvided, snapshot: DroppableStateSnapshot) => (
                    <div className={`flex flex-col gap-2 transition-all duration-200 ease-in ${snapshot.isDraggingOver ? 'bg-blue-100' : 'bg-white'}`} {...provided.droppableProps} ref={provided.innerRef}>
                        {tasks.map((task: any, index: number) => (
                            <Draggable key={task.id} draggableId={task.id} index={index}>
                                {(provided: DraggableProvided, snapshot: DraggableStateSnapshot) => (
                                    <div {...provided.draggableProps} ref={provided.innerRef} className={`flex gap-2 items-center px-3 py-2 border-[1px] border-gray-200 rounded-sm ${snapshot.isDragging ? 'bg-green-100' : 'bg-white'}`}>
                                        <div className="flex items-center justify-center" {...provided.dragHandleProps}>
                                            <DragHandleIcon width={20} height={20} />
                                        </div>
                                        {task.content}
                                    </div>
                                )}
                            </Draggable>
                        ))}
                        {provided.placeholder}
                    </div>
                )}
            </StrictModeDroppable>
        </div>
    );
};

interface IFormBuilderProps {
    formId: string;
    formData: any;
}

export default function FormBuilder({ formId, formData }: IFormBuilderProps) {
    const dispatch = useAppDispatch();
    const initialData = {
        tasks: {
            'task-1': { id: 'task-1', content: 'Task 1' },
            'task-2': { id: 'task-2', content: 'Task 2' },
            'task-3': { id: 'task-3', content: 'Task 3' },
            'task-4': { id: 'task-4', content: 'Task 4' }
        },
        columns: {
            'column-1': {
                id: 'column-1',
                title: 'To-do',
                tasks: ['task-2', 'task-3', 'task-4']
            },
            'column-2': {
                id: 'column-2',
                title: 'In-Progress',
                tasks: ['task-1']
            }
        },
        columnOrder: ['column-1', 'column-2']
    };

    const [state, setState] = useState<{ tasks: any; columns: any; columnOrder: Array<string> }>({ ...initialData });

    const [formTitle, setFormTitle] = useState(formData?.title ?? builderConstants.FormTitle);

    const formFields = useAppSelector(selectFormBuilderFields);

    const blocks: any = Object.values(formFields);

    const reorder = (list: Array<any>, startIndex: number, endIndex: number) => {
        const result = Array.from(list);
        const [removed] = result.splice(startIndex - 1, 1);
        result.splice(endIndex - 1, 0, removed);
        return result;
    };

    const onDragEndHandler: OnDragEndResponder = (result: DropResult) => {
        if (!result.destination) {
            return;
        }
        const items = reorder(blocks, result.source.index, result.destination.index);
        dispatch(setFields(items));
    };

    const addBlockHandler = (block: any) => {
        const newBlock = {
            id: uuidv4(),
            tag: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
            type: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
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
        // setBlocks(updatedBlocks);
    };

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
                id: uuidv4(),
                tag: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
                type: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
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
            // setBlocks([{ ...newBlock }]);
        }
    }, [blocks]);

    // Don't remove these methods
    const onTestDragStartHandler: OnDragStartResponder = (start: DragStart, provided: ResponderProvided) => {};

    const onTestDragUpdateHandler: OnDragUpdateResponder = (update: DragUpdate, provided: ResponderProvided) => {};

    const onTestDragEndHandler: OnDragEndResponder = (result: DropResult, provided: ResponderProvided) => {
        const { destination, source, draggableId } = result;
        console.log(destination, source);
        if (!destination) return;

        if (destination.droppableId === source.droppableId && destination.index === source.index) return;

        const column = state.columns[source.droppableId];
        const newTasksId = Array.from(column.tasks);
        newTasksId.splice(source.index, 1);
        newTasksId.splice(destination.index, 0, draggableId);
        console.log(column, newTasksId);

        const newColumn = {
            ...column,
            tasks: newTasksId
        };

        setState({ ...state, columns: { ...state.columns, [newColumn.id]: newColumn } });
    };

    return (
        <div className="min-h-calc-68 w-full bg-white px-5 lg:px-10 py-10">
            <h1 className="sh1">Start building your form</h1>
            <p className="body4">Click anywhere and start typing</p>
            <FormBuilderTitleInput title={formTitle} handleFormTitleChange={(e: any) => setFormTitle(e.target.value)} />
            {/* TODO: Fix description component */}
            <HotkeysProvider initiallyActiveScopes={['builder']}>
                <FormBuilderHotkeysHookListener scopes="builder">
                    <DragDropContext onDragEnd={onDragEndHandler}>
                        <StrictModeDroppable droppableId="droppable">
                            {(provided: DroppableProvided) => (
                                <div {...provided.droppableProps} ref={provided.innerRef}>
                                    {blocks.map((block: any) => {
                                        const position = blocks.map((b: any) => b.id).indexOf(block.id) + 1;
                                        return (
                                            <FormBuilderBlock
                                                block={block}
                                                key={block.id}
                                                position={position}
                                                id={block.id}
                                                type={block.type}
                                                tag={block.tag}
                                                html={block.html}
                                                imageUrl={block.imageUrl}
                                                formId={formId}
                                                dispatch={dispatch}
                                                addBlock={addBlockHandler}
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
                    {/* TODO: Don't use below. This is for testing only and don't remove it as well */}
                    <DragDropContext onDragStart={onTestDragStartHandler} onDragUpdate={onTestDragUpdateHandler} onDragEnd={onTestDragEndHandler}>
                        <div className="flex flex-row">
                            {state.columnOrder.map((columnId: string, index: number) => {
                                const column = state.columns[columnId];
                                const tasks = column.tasks.map((taskId: string) => state.tasks[taskId]);

                                return <Column key={column.id} column={column} tasks={tasks} />;
                            })}
                        </div>
                    </DragDropContext>
                </FormBuilderHotkeysHookListener>
            </HotkeysProvider>
        </div>
    );
}
