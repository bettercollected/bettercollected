import React, { useCallback, useEffect } from 'react';

import { batch } from 'react-redux';
import { ActionCreators } from 'redux-undo';

import eventBus from '@app/lib/event-bus';
import EventBusEventType from '@app/models/enums/eventBusEnum';
import { resetBuilderMenuState } from '@app/store/form-builder/actions';
import { selectBuilderFutureState, selectBuilderPastState, selectBuilderState } from '@app/store/form-builder/selectors';
import { IBuilderState, IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { focusElementByIdWithDelay } from '@app/utils/domUtils';
import { isMultipleChoice } from '@app/utils/formBuilderBlockUtils';

export default function HistoryKeyListener({ children }: React.PropsWithChildren) {
    const dispatch = useAppDispatch();
    const builderPastState: IBuilderState | null = useAppSelector(selectBuilderPastState);
    const builderFutureState: IBuilderState | null = useAppSelector(selectBuilderFutureState);
    const builderstate: IBuilderState = useAppSelector(selectBuilderState);

    const onKeyDownCallback = useCallback(
        (event: KeyboardEvent) =>
            batch(() => {
                if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === 'z') {
                    eventBus.emit(EventBusEventType.History.UndoRedoStart);
                    dispatch(ActionCreators.undo());
                    dispatch(resetBuilderMenuState());
                    const activeField: IFormFieldState | null = builderPastState?.fields[builderPastState?.activeFieldId];
                    if (isMultipleChoice(activeField?.type)) {
                        focusElementByIdWithDelay(`choice-${activeField?.properties?.activeChoiceId}`);
                    } else {
                        focusElementByIdWithDelay(`item-${builderPastState?.activeFieldId}`);
                    }
                    setTimeout(() => eventBus.emit(EventBusEventType.History.UndoRedoCompleted), 50);
                } else if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === 'y') {
                    eventBus.emit(EventBusEventType.History.UndoRedoStart);
                    dispatch(ActionCreators.redo());
                    dispatch(resetBuilderMenuState());

                    const activeField = builderFutureState?.fields[builderFutureState?.activeFieldId];
                    if (isMultipleChoice(activeField?.type)) {
                        focusElementByIdWithDelay(`choice-${activeField?.properties?.activeChoiceId}`);
                    } else {
                        focusElementByIdWithDelay(`item-${builderFutureState?.activeFieldId}`);
                    }
                    setTimeout(() => eventBus.emit(EventBusEventType.History.UndoRedoCompleted), 50);
                }
            }),
        [builderFutureState?.activeFieldId, builderFutureState?.fields, builderPastState, dispatch]
    );

    useEffect(() => {
        document.addEventListener('keydown', onKeyDownCallback);

        return () => {
            document.removeEventListener('keydown', onKeyDownCallback);
        };
    }, [onKeyDownCallback, builderPastState, builderFutureState]);

    return <div>{children}</div>;
}
