import React from 'react';

import { FormBuilderCommands } from '@app/models/enums/FormBuilderCommands';

import ICommandListener from '../listeners/interfaces/ICommandListener';

type BuilderContext = 'SPOTLIGHT' | 'BUILDER' | 'PREVIEW' | 'FIELD' | 'COMMAND';

export default class CommandManager {
    private static commands: Record<string, ICommandListener> = {};
    private static activeContext: BuilderContext = 'BUILDER';

    static registerCommand(shortcut: string, command: ICommandListener) {
        this.commands[shortcut] = command;
    }

    static unregisterCommand(shortcut: string) {
        delete this.commands[shortcut];
    }

    static getShortcutFromEvent(event: React.KeyboardEvent): FormBuilderCommands | string | null {
        if ((event.ctrlKey || event.metaKey) && (event.key === 'k' || event.key === 'K')) {
            return FormBuilderCommands.SPOTLIGHT;
        }
        if (event.key === 'Enter') {
            return FormBuilderCommands.ENTER;
        }
        if (event.key === 'ArrowUp') {
            return FormBuilderCommands.ARROW_UP;
        }
        if (event.key === 'ArrowDown') {
            return FormBuilderCommands.ARROW_DOWN;
        }
        // Add more shortcut checks as needed
        return null;
    }

    static executeCommand(shortcut: string | FormBuilderCommands, callback?: Function) {
        const command = this.commands[shortcut];

        if (shortcut === FormBuilderCommands.ENTER && (this.activeContext === 'SPOTLIGHT' || this.activeContext === 'COMMAND' || this.activeContext === 'PREVIEW')) {
            // Do nothing
            return;
        }

        if (command) {
            command.execute(callback);
        }
    }
}
