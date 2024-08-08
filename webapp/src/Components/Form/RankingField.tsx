import React from 'react';

import { FormFieldProps } from '@Components/Form/BetterCollectedForm';
import { StrictModeDroppable } from '@Components/FormBuilder/StrictModeDroppable';
import { FieldRequired } from '@Components/ui/FieldRequired';
import { Code } from '@mui/icons-material';
import { DragDropContext, Draggable, DraggableProvided, DraggableStateSnapshot, DroppableProvided, DropResult } from 'react-beautiful-dnd';

import { addAnswer, selectAnswer } from '@app/store/fill-form/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { reorder } from '@app/utils/arrayUtils';

export default function RankingField({ field, enabled, ans }: FormFieldProps) {
    const rankAnswer = useAppSelector(selectAnswer(field.id));
    const dispatch = useAppDispatch();
    const onDragEnd = (result: DropResult) => {
        if (!result.destination) {
            return;
        }
        const answer: any = {
            field: {
                id: field.id
            }
        };
        answer.choices = {
            values: [...reorder(rankAnswer?.choices?.values || field?.properties?.choices || [], result.source.index, result.destination.index)]
        };
        dispatch(addAnswer(answer));
    };

    return (
        // @ts-ignore
        <DragDropContext onDragEnd={onDragEnd}>
            <StrictModeDroppable droppableId="ranking">
                {(provided: DroppableProvided) => (
                    <div {...provided.droppableProps} ref={provided.innerRef} className="relative !mb-0 flex w-fit min-w-[200px] flex-col gap-3">
                        {field?.validations?.required && <FieldRequired className=" -right-5" />}
                        {(ans?.choices?.values || rankAnswer?.choices?.values || field?.properties?.choices)?.map((choice: any, index: number) => (
                            // @ts-ignore
                            <Draggable key={choice.id} draggableId={choice.id} index={index} isDragDisabled={!enabled}>
                                {(provided: DraggableProvided, snapshot: DraggableStateSnapshot) => (
                                    <div className={`body4 flex gap-2 rounded border bg-white px-4 py-2`} {...provided.draggableProps} ref={provided.innerRef}>
                                        <div {...provided.dragHandleProps} className="rotate-90">
                                            <Code />
                                        </div>
                                        {choice.value}
                                    </div>
                                )}
                            </Draggable>
                        ))}
                        {provided.placeholder}
                    </div>
                )}
            </StrictModeDroppable>
        </DragDropContext>
    );
}
