import { useState } from 'react';

import { StrictModeDroppable } from '@Components/FormBuilder/StrictModeDroppable';
import { Code } from '@mui/icons-material';
import { DragDropContext, Draggable, DraggableProvided, DropResult, DroppableProvided } from 'react-beautiful-dnd';

import { StandardFormQuestionDto } from '@app/models/dtos/form';
import { reorder } from '@app/utils/arrayUtils';

export default function RankingField({ field }: { field: StandardFormQuestionDto }) {
    const onDragEnd = (result: DropResult) => {
        if (!result.destination) {
            return;
        }
        setRankingAnswer([...reorder(rankAnswer, result.source.index, result.destination.index)]);
    };
    const [rankAnswer, setRankingAnswer] = useState(field?.properties?.choices || []);

    return (
        <DragDropContext onDragEnd={onDragEnd}>
            <StrictModeDroppable droppableId="ranking">
                {(provided: DroppableProvided) => (
                    <div {...provided.droppableProps} ref={provided.innerRef} className="w-full  flex flex-col gap-3">
                        {rankAnswer.map((choice: any, index: number) => (
                            <Draggable key={choice.id} draggableId={choice.id} index={index}>
                                {(provided: DraggableProvided) => (
                                    <div className="rounded px-4 py-2 flex gap-2 bg-white border" {...provided.draggableProps} ref={provided.innerRef}>
                                        <div {...provided.dragHandleProps} className="rotate-90">
                                            <Code />
                                        </div>
                                        <span>{index + 1}.</span>
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
