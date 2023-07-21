import React from 'react';

import { DragDropContext, DragStart, DragUpdate, DropResult, DroppableProvided, DroppableStateSnapshot, OnDragEndResponder, OnDragStartResponder, OnDragUpdateResponder, ResponderProvided } from 'react-beautiful-dnd';

import { StrictModeDroppable } from '../StrictModeDroppable';

interface IBuilderDragDropContextProps<TModel> {
    Component: React.ComponentType<any>;
    componentAttrs: Record<string, TModel>;
    droppableId: string;
    droppableItems: Array<{ id: string; [props: string]: any }>;
    droppableClassName?: string;
    onDragStartHandlerCallback: OnDragStartResponder;
    onDragUpdateHandlerCallback: OnDragUpdateResponder;
    onDragEndHandlerCallback: OnDragEndResponder;
}

export default function BuilderDragDropContext({ Component, componentAttrs, droppableId, droppableItems, droppableClassName = '', onDragStartHandlerCallback, onDragUpdateHandlerCallback, onDragEndHandlerCallback }: IBuilderDragDropContextProps<any>) {
    const onDragStartHandler: OnDragStartResponder = (start: DragStart, provided: ResponderProvided) => {
        if (!start.source) return;

        onDragStartHandlerCallback(start, provided);
    };

    const onDragUpdateHandler: OnDragUpdateResponder = (update: DragUpdate, provided: ResponderProvided) => {
        if (!update.destination || !update.source) return;

        onDragUpdateHandlerCallback(update, provided);
    };

    const onDragEndHandler: OnDragEndResponder = (result: DropResult, provided: ResponderProvided) => {
        if (!result.destination || !result.source) return;

        onDragEndHandlerCallback(result, provided);
    };

    return (
        <DragDropContext onDragStart={onDragStartHandler} onDragUpdate={onDragUpdateHandler} onDragEnd={onDragEndHandler}>
            <StrictModeDroppable droppableId={droppableId}>
                {(provided: DroppableProvided, snapshot: DroppableStateSnapshot) => (
                    <div className={`flex flex-col gap-2 transition-all duration-200 ease-in ${snapshot.isDraggingOver ? 'bg-black-100 bg-opacity-30 rounded' : 'bg-white'} ${droppableClassName}`} {...provided.droppableProps} ref={provided.innerRef}>
                        {droppableItems.map((item: any) => (
                            <Component key={item.id} item={item} {...componentAttrs} />
                        ))}
                        {provided.placeholder}
                    </div>
                )}
            </StrictModeDroppable>
        </DragDropContext>
    );
}
