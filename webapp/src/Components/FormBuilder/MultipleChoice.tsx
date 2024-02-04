import React from 'react';

import PlusIcon from '@Components/Common/Icons/Common/Plus';
import DragHandleIcon from '@Components/Common/Icons/FormBuilder/DragHandle';
import StartAdornmentInputField from '@Components/FormBuilder/StartAdornmentInputField';
import { StrictModeDroppable } from '@Components/FormBuilder/StrictModeDroppable';
import { FieldRequired } from '@Components/UI/FieldRequired';
import { GridCloseIcon } from '@mui/x-data-grid';
import { DragDropContext, Draggable, DropResult, DroppableProvided } from 'react-beautiful-dnd';
import { useDispatch } from 'react-redux';

import useUserTypingDetection from '@app/lib/hooks/use-user-typing-detection';
import useUndoRedo from '@app/lib/use-undo-redo';
import { setActiveChoice, setAddNewChoice, setUpdateField } from '@app/store/form-builder/actions';
import { IFormFieldState } from '@app/store/form-builder/types';
import { reorder } from '@app/utils/arrayUtils';
import { createNewChoice } from '@app/utils/formBuilderBlockUtils';


interface IMultipleChoiceProps {
    field: IFormFieldState;
    id: string;
    position: number;
}

export default function MultipleChoice({ field, id }: IMultipleChoiceProps) {
    const dispatch = useDispatch();
    const { handleUserTypingEnd } = useUserTypingDetection();
    const { isUndoRedoInProgress } = useUndoRedo();
    const handleChoiceValueChange = (id: string, value: string) => {
        if (isUndoRedoInProgress) return;
        dispatch(
            setUpdateField({
                ...field,
                properties: {
                    ...field.properties,
                    // @ts-ignore
                    choices: { ...field.properties?.choices, [id]: { ...field.properties?.choices[id], id, value } }
                }
            })
        );
        handleUserTypingEnd();
    };
    const addChoice = (index: number) => {
        //@ts-ignore
        dispatch(setAddNewChoice({ fieldId: field.id, choice: createNewChoice(index + 1) }));
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
        <div id={id} className="flex w-full items-start justify-start focus-visible:!outline-none focus-visible:!border-none ">
            <DragDropContext onDragEnd={onDragEnd}>
                <StrictModeDroppable droppableId="droppable-multiple-choice">
                    {(provided: DroppableProvided) => (
                        <div {...provided.droppableProps} ref={provided.innerRef} className="w-full">
                            {Object.values(field.properties?.choices || {}).map((choice, index) => {
                                // @ts-ignore
                                return (
                                    <Draggable key={`${choice.id}-${choice.position}`} draggableId={choice.id} index={index}>
                                        {(provided) => (
                                            <div className="flex gap-5 mb-3 items-start justify-start focus-visible:outline-none focus-visible:border-none" {...provided.draggableProps} ref={provided.innerRef}>
                                                <div className="relative flex flex-row-reverse items-center gap-2">
                                                    {index === 0 && field?.validations?.required && <FieldRequired className="top-2 -right-5" />}
                                                    <div className="flex items-center gap-2 justify-center">
                                                        <div
                                                            onClick={() => {
                                                                addChoice(index);
                                                            }}
                                                            className="flex items-center justify-center rounded z-[10] text-gray-500 bg-gray-200 h-5 w-5 cursor-pointer"
                                                        >
                                                            <PlusIcon className="h-3 w-3" />
                                                        </div>
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
                                                    </div>
                                                    <StartAdornmentInputField
                                                        type={field.type}
                                                        // focus={builderState.fields[builderState.activeFieldId]?.properties?.activeChoiceIndex === choice.position && field.id === builderState.activeFieldId}
                                                        id={`choice-${choice.id}`}
                                                        onChangeCallback={(event) => {
                                                            handleChoiceValueChange(choice.id, event.target.value);
                                                        }}
                                                        onFocusCallback={() => {
                                                            dispatch(
                                                                setActiveChoice({
                                                                    id: choice.id,
                                                                    position: choice.position
                                                                })
                                                            );
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
    );
}