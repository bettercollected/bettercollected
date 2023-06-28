import React, { useState } from 'react';

import { StrictModeDroppable } from '@Components/FormBuilders/StrictModeDroppable';
import { DragDropContext, Draggable, DraggableProvided, DropResult, DroppableProvided, OnDragEndResponder, ResponderProvided } from 'react-beautiful-dnd';

export default function FormBuilder() {
    const [blocks, setBlocks] = useState<any>([
        { id: 'block-1', content: 'Item 1' },
        { id: 'block-2', content: 'Item 2' }
    ]);

    const onDragEndHandler: OnDragEndResponder = (result: DropResult, provided: ResponderProvided) => {
        if (!result.destination) return;

        const newBlocks = Array.from(blocks);
        const [reorderedBlock] = newBlocks.splice(result.source.index, 1);
        newBlocks.splice(result.destination.index, 0, reorderedBlock);

        setBlocks(newBlocks);
    };

    return (
        <div className="min-h-calc-68 w-full bg-white px-5 lg:px-10 py-10">
            <h1 className="sh1">Start building your form</h1>
            <p className="body4">Click anywhere and start typing</p>
            <DragDropContext onDragEnd={onDragEndHandler}>
                <StrictModeDroppable droppableId="droppable">
                    {(provided: DroppableProvided) => (
                        <div {...provided.droppableProps} ref={provided.innerRef}>
                            {blocks.map((block: any, index: number) => (
                                <Draggable key={block.id} draggableId={block.id} index={index}>
                                    {(provided: DraggableProvided) => (
                                        <div ref={provided.innerRef} {...provided.draggableProps} {...provided.dragHandleProps}>
                                            {block.content}
                                        </div>
                                    )}
                                </Draggable>
                            ))}
                            {provided.placeholder}
                        </div>
                    )}
                </StrictModeDroppable>
            </DragDropContext>
        </div>
    );
}
