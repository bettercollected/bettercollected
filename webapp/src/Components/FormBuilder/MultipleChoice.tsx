import React from 'react';

import DragHandleIcon from '@Components/Common/Icons/DragHandle';
import PlusIcon from '@Components/Common/Icons/Plus';
import StartAdornmentInputField from '@Components/FormBuilder/StartAdornmentInputField';
import { StrictModeDroppable } from '@Components/FormBuilder/StrictModeDroppable';
import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { TextField } from '@mui/material';
import { GridCloseIcon } from '@mui/x-data-grid';
import { DragDropContext, Draggable, DropResult, DroppableProvided } from 'react-beautiful-dnd';
import { useDispatch } from 'react-redux';

import { addField, setFieldTitle } from '@app/store/form-builder/slice';
import { reorder } from '@app/utils/arrayUtils';

interface IMultipleChoiceProps {
    field: any;
}

export default function MultipleChoice({ field }: IMultipleChoiceProps) {
    const dispatch = useDispatch();
    const addFieldTitle = (title: string) => {
        dispatch(setFieldTitle({ fieldId: field.id, title: title }));
    };

    const handleChoiceValueChange = (id: string, value: string) => {
        dispatch(addField({ ...field, choices: { ...field.choices, [id]: { id, value } } }));
    };

    const addChoice = (index: number) => {
        const id = uuidv4();
        const newChoices = Object.values(field.choices);
        newChoices.splice(index + 1, 0, { id, value: '' });
        const choices: any = {};
        newChoices.forEach((choice: any) => {
            choices[choice.id] = choice;
        });
        dispatch(addField({ ...field, choices: choices }));
    };

    const deleteChoice = (id: string) => {
        const choices = { ...field.choices };
        delete choices[id];
        dispatch(addField({ ...field, choices: { ...choices } }));
    };

    const onDragEnd = (result: DropResult) => {
        if (!result.destination) {
            return;
        }

        const items = reorder(Object.values(field.choices), result.source.index + 1, result.destination.index + 1);
        const choices: any = {};
        items.forEach((item) => {
            choices[item.id] = item;
        });
        dispatch(addField({ ...field, choices: { ...choices } }));
    };

    return (
        <div>
            {field.title !== undefined && (
                <div>
                    <TextField
                        onChange={(event) => {
                            addFieldTitle(event.target.value);
                        }}
                        placeholder="Question Title"
                        value={field.title}
                        fullWidth
                        variant="standard"
                        inputMode="text"
                        inputProps={{
                            style: {
                                padding: 0,
                                paddingBottom: 0,
                                height: 40,
                                fontSize: 18,
                                fontWeight: 600,
                                content: 'none',
                                letterSpacing: 1
                            }
                        }}
                        InputProps={{ sx: { ':before': { content: 'none' } } }}
                    />
                </div>
            )}
            <div className="flex w-full items-start justify-start">
                <DragDropContext onDragEnd={onDragEnd}>
                    <StrictModeDroppable droppableId="choices">
                        {(provided: DroppableProvided) => (
                            <div {...provided.droppableProps} ref={provided.innerRef} className="w-full">
                                {Object.values(field.choices || {}).map((choice: any, index) => {
                                    return (
                                        <Draggable key={choice.id} draggableId={choice.id} index={index}>
                                            {(provided) => (
                                                <div className="flex gap-5 mb-3 items-start justify-start" {...provided.draggableProps} ref={provided.innerRef}>
                                                    <div className="relative">
                                                        <div className="absolute flex items-center gap-2 justify-center -top-2 -right-2">
                                                            {Object.values(field.choices).length > 1 && (
                                                                <div
                                                                    onClick={() => {
                                                                        deleteChoice(choice.id);
                                                                    }}
                                                                    className="flex items-center justify-center rounded z-[10] p-2 text-gray-500 bg-gray-200 h-5 w-5 cursor-pointer"
                                                                >
                                                                    <GridCloseIcon className="h-3 w-3" />
                                                                </div>
                                                            )}
                                                            <div className="flex items-center justify-center rounded z-[10] text-gray-500 bg-gray-200 h-5 w-5 cursor-pointer" {...provided.dragHandleProps}>
                                                                <DragHandleIcon className="h-3 w-3" />
                                                            </div>
                                                            <div
                                                                onClick={() => {
                                                                    addChoice(index);
                                                                }}
                                                                className="flex items-center justify-center rounded z-[10] text-gray-500 bg-gray-200 h-5 w-5 cursor-pointer"
                                                            >
                                                                <PlusIcon className="h-3 w-3" />
                                                            </div>
                                                        </div>

                                                        <StartAdornmentInputField
                                                            type={field.tag}
                                                            onChange={(event) => {
                                                                handleChoiceValueChange(choice.id, event.target.value);
                                                            }}
                                                            value={field.choices[choice?.id]?.value}
                                                        />
                                                    </div>
                                                </div>
                                            )}
                                        </Draggable>
                                    );
                                })}
                                {provided.placeholder}
                            </div>
                        )}
                    </StrictModeDroppable>
                </DragDropContext>

                {field.title === undefined && (
                    <div
                        className="text-gray-400 w-full mt-2 cursor-pointer"
                        onClick={() => {
                            addFieldTitle('');
                        }}
                    >
                        Add title
                    </div>
                )}
            </div>
        </div>
    );
}
