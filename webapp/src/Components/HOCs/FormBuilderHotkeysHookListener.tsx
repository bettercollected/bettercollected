import React, { useState } from 'react';

import { useHotkeys } from 'react-hotkeys-hook';

interface IHotkeysHookListenerProps {
    enableHotkeys?: boolean;
    scopes: string;
    children: React.ReactNode | React.ReactNode[];
}

export default function FormBuilderHotkeysHookListener({ children, scopes, enableHotkeys = true }: IHotkeysHookListenerProps) {
    const [hotkeysOptions, setHotkeysOptions] = useState({
        enabled: enableHotkeys,
        scopes
    });

    useHotkeys(
        'enter',
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log('Dispatch enter event!');
        },
        hotkeysOptions
    );

    useHotkeys(
        'escape',
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log('Dispatch escape event!');
        },
        hotkeysOptions
    );

    useHotkeys(
        ['up', 'down', 'left', 'right'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log(`Dispatch select another block ${keyboardEvent.key} event!`);
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+z', 'meta+z'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log('Dispatch undo event!');
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+y', 'meta+y'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log('Dispatch redo event!');
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+0', 'meta+alt+0'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log('Dispatch create text event!');
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+1', 'meta+alt+1'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log('Dispatch create h1 heading event!');
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+2', 'meta+alt+2'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log('Dispatch create h2 heading event!');
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+3', 'meta+alt+3'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log('Dispatch create h3 heading event!');
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+4', 'meta+alt+4'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log('Dispatch create to-do checklist event!');
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+5', 'meta+alt+5'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log('Dispatch create a bulleted list event!');
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+6', 'meta+alt+6'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log('Dispatch create a numbered list event!');
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+7', 'meta+alt+7'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log('Dispatch create a toggle list event!');
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+8', 'meta+alt+8'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log('Dispatch create a code block event!');
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+9', 'meta+alt+9'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log('Dispatch create a new page break event!');
        },
        hotkeysOptions
    );

    useHotkeys(
        ['shift+up', 'shift+down'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log(`Dispatch expand the selection ${keyboardEvent.key} event!`);
        },
        hotkeysOptions
    );

    useHotkeys(
        ['backspace', 'delete'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log(`Dispatch ${keyboardEvent.key} event!`);
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+d', 'meta+d'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log(`Dispatch delete a block event!`);
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+slash', 'meta+slash'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log(`Dispatch edit or change a block event!`);
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+up', 'ctrl+shift+down', 'ctrl+shift+left', 'ctrl+shift+right', 'meta+shift+up', 'meta+shift+down', 'meta+shift+left', 'meta+shift+right'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            console.log(`Dispatch move a block ${keyboardEvent.key} event!`);
        },
        hotkeysOptions
    );

    return <>{children}</>;
}
