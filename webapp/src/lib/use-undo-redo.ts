import { useLayoutEffect, useState } from 'react';

import EventBusEventType from '@app/models/enums/eventBusEnum';

import eventBus from './event-bus';


export default function useUndoRedo() {
    const [isUndoRedoInProgress, setIsUndoRedoInProgress] = useState(false);

    const startUndoRedoAction = () => {
        setIsUndoRedoInProgress(true);
    };

    const completeUndoRedoAction = () => {
        setIsUndoRedoInProgress(false);
    };

    useLayoutEffect(() => {
        eventBus.on(EventBusEventType.History.UndoRedoStart, startUndoRedoAction);
        eventBus.on(EventBusEventType.History.UndoRedoCompleted, completeUndoRedoAction);

        return () => {
            eventBus.removeListener(EventBusEventType.History.UndoRedoStart, startUndoRedoAction);
            eventBus.removeListener(EventBusEventType.History.UndoRedoCompleted, completeUndoRedoAction);
        };
    }, []);

    return { isUndoRedoInProgress };
}