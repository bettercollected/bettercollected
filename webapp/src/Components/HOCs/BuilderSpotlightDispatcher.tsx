import React, { useEffect } from 'react';

import { useModal } from '@app/components/modal-views/context';
import ArrowCommandListener from '@app/lib/builders/listeners/implementations/ArrowCommandListener';
import EnterCommandListener from '@app/lib/builders/listeners/implementations/EnterCommandListener';
import SpotlightCommandListener from '@app/lib/builders/listeners/implementations/SpotlightCommandListener';
import ICommandListener from '@app/lib/builders/listeners/interfaces/ICommandListener';
import CommandManager from '@app/lib/builders/managers/CommandManager';
import { FormBuilderCommands } from '@app/models/enums/FormBuilderCommands';
import { IBuilderStateProps } from '@app/store/form-builder/types';

interface IBuilderSpotlightDispatcherProps {
    children: React.ReactNode | React.ReactNode[];
    state: IBuilderStateProps;
}

export default function BuilderSpotlightDispatcher({ state, children }: IBuilderSpotlightDispatcherProps) {
    const { openModal } = useModal();

    const spotlightCallback = () => {
        openModal('FORM_BUILDER_SPOTLIGHT_VIEW', state);
    };

    // Define the command listeners and their respective shortcuts
    const commandListeners: Record<FormBuilderCommands | string, { listener: ICommandListener; callback?: Function }> = {
        [FormBuilderCommands.SPOTLIGHT]: {
            listener: new SpotlightCommandListener(),
            callback: spotlightCallback
        },
        [FormBuilderCommands.ENTER]: {
            listener: new EnterCommandListener(state)
        },
        [FormBuilderCommands.ARROW_UP]: {
            listener: new ArrowCommandListener(state, FormBuilderCommands.ARROW_UP)
        },
        [FormBuilderCommands.ARROW_DOWN]: {
            listener: new ArrowCommandListener(state, FormBuilderCommands.ARROW_DOWN)
        }
    };

    const handleKeyDown = (event: React.KeyboardEvent) => {
        const shortcut = CommandManager.getShortcutFromEvent(event);
        if (shortcut) {
            // Execute the command for the matching shortcut
            CommandManager.executeCommand(shortcut, commandListeners[shortcut].callback);
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
