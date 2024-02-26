import React, { useEffect } from 'react';

import { batch } from 'react-redux';

import { useModal } from '@app/components/modal-views/context';
import SpotlightCommandListener from '@app/lib/builders/listeners/implementations/SpotlightCommandListener';
import ICommandListener from '@app/lib/builders/listeners/interfaces/ICommandListener';
import CommandManager from '@app/lib/builders/managers/CommandManager';
import { FormBuilderCommands } from '@app/models/enums/FormBuilderCommands';
import { resetBuilderMenuState, setBuilderMenuState, setBuilderState } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IBuilderStateProps } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { AppDispatch } from '@app/store/store';


interface IBuilderSpotlightDispatcherProps {
    children: React.ReactNode | React.ReactNode[];
}

export default function BuilderKeyAndEventListener({ children }: IBuilderSpotlightDispatcherProps) {
    const { openModal } = useModal();

    const dispatch: AppDispatch = useAppDispatch();
    const builderState = useAppSelector(selectBuilderState);
    const state: IBuilderStateProps = {
        builderState,
        setBuilderState,
        dispatch
    };

    const spotlightCallback = () => {
        batch(() => {
            dispatch(resetBuilderMenuState());
            dispatch(
                setBuilderMenuState({
                    spotlightField: {
                        isOpen: true,
                        afterFieldUuid: Object.keys(builderState.fields).at(builderState.activeFieldIndex) ?? ''
                    }
                })
            );
        });
        openModal('FORM_BUILDER_SPOTLIGHT_VIEW', state);
    };

    // Define the command listeners and their respective shortcuts
    const commandListeners: Record<
        FormBuilderCommands | string,
        {
            listener: ICommandListener;
            callback?: Function;
        }
    > = {
        [FormBuilderCommands.SPOTLIGHT]: {
            listener: new SpotlightCommandListener(),
            callback: spotlightCallback
        }
        // [FormBuilderCommands.ENTER]: {
        //     listener: new EnterCommandListener(state)
        // },
        // [FormBuilderCommands.ARROW_UP]: {
        //     listener: new ArrowCommandListener(state, FormBuilderCommands.ARROW_UP)
        // },
        // [FormBuilderCommands.ARROW_DOWN]: {
        //     listener: new ArrowCommandListener(state, FormBuilderCommands.ARROW_DOWN)
        // }
    };

    const handleKeyDown = (event: React.KeyboardEvent) => {
        const shortcut = CommandManager.getShortcutFromEvent(event);
        if (shortcut) {
            // Execute the command for the matching shortcut
            CommandManager.executeCommand(shortcut, event, commandListeners[shortcut].callback);
        }
    };

    useEffect(() => {
        Object.keys(commandListeners).forEach((key: string) => {
            CommandManager.registerCommand(key, commandListeners[key].listener);
        });

        return () => {
            Object.keys(commandListeners).forEach((key: string) => {
                CommandManager.unregisterCommand(key);
            });
        };
    }, []);

    return <div onKeyDown={handleKeyDown}>{children}</div>;
}