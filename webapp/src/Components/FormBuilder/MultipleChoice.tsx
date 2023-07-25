import React from 'react';

import DragHandleIcon from '@Components/Common/Icons/DragHandle';
import PlusIcon from '@Components/Common/Icons/Plus';
import StartAdornmentInputField from '@Components/FormBuilder/StartAdornmentInputField';
import { StrictModeDroppable } from '@Components/FormBuilder/StrictModeDroppable';
import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { GridCloseIcon } from '@mui/x-data-grid';
import { DragDropContext, Draggable, DropResult, DroppableProvided } from 'react-beautiful-dnd';
import { useDispatch } from 'react-redux';

import { setUpdateField } from '@app/store/form-builder/actions';
import { IFormFieldState } from '@app/store/form-builder/types';
import { reorder } from '@app/utils/arrayUtils';

interface IMultipleChoiceProps {
    field: IFormFieldState;
    id: any;
}

export default function MultipleChoice({ field, id }: IMultipleChoiceProps) {
    const dispatch = useDispatch();

    const handleChoiceValueChange = (id: string, value: string) => {
        dispatch(
            setUpdateField({
                ...field,
                properties: { ...field.properties?.choices, choices: { ...field.properties?.choices, [id]: { id, value } } }
            })
        );
    };

    const addChoice = (index: number) => {
        const id = uuidv4();
        const newChoices = Object.values(field.properties?.choices || {});
        newChoices.splice(index + 1, 0, { id, value: '' });
        const choices: any = {};
        newChoices.forEach((choice: any) => {
            choices[choice.id] = choice;
        });
        dispatch(setUpdateField({ ...field, properties: { ...field.properties, choices: choices } }));
    };

    const deleteChoice = (id: string) => {
        const choices = { ...field.properties?.choices };
        delete choices[id];
        dispatch(setUpdateField({ ...field, properties: { ...field.properties, choices: { ...choices } } }));
    };

    const onDragEnd = (result: DropResult) => {
        if (!result.destination) {
            return;
        }

        const items = reorder(Object.values(field.properties?.choices || {}), result.source.index, result.destination.index);
        const choices: any = {};
        items.forEach((item) => {
            choices[item.id] = item;
        });
        dispatch(
            setUpdateField({
                ...field,
                properties: { ...field.properties, choices: { ...choices } }
            })
        );
    };

    return (
        <div>
            <div className="flex w-full items-start justify-start">
                <DragDropContext onDragEnd={onDragEnd}>
                    <StrictModeDroppable droppableId="choices">
                        {(provided: DroppableProvided) => (
                            <div {...provided.droppableProps} ref={provided.innerRef} className="w-full">
                                {Object.values(field.properties?.choices || {}).map((choice: any, index) => {
                                    // @ts-ignore
                                    return (
                                        <Draggable key={choice.id} draggableId={choice.id} index={index}>
                                            {(provided) => (
                                                <div className="flex gap-5 mb-3 items-start justify-start" {...provided.draggableProps} ref={provided.innerRef}>
                                                    <div className="relative flex flex-row-reverse items-center gap-2">
                                                        {index === 0 && field?.validations?.required && <div className="top-2 -right-5">*</div>}
                                                        <div className="flex items-center gap-2 justify-center">
                                                            {Object.values(field.properties?.choices || {}).length > 1 && (
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
                                                            type={field.type}
                                                            id={id}
                                                            onChange={(event) => {
                                                                handleChoiceValueChange(choice.id, event.target.value);
                                                            }}
                                                            // @ts-ignore
                                                            value={field?.properties?.choices[choice?.id]?.value || ''}
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
            </div>
        </div>
    );
}
