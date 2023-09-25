import React, { useState } from 'react';

import { useHotkeys } from 'react-hotkeys-hook';

interface IHotkeysHookListenerProps {
    addBlock?: any;
    enableHotkeys?: boolean;
    scopes: string;
    children: React.ReactNode | React.ReactNode[];
}

export default function FormBuilderHotkeysHookListener({ children, scopes, addBlock = () => {}, enableHotkeys = true }: IHotkeysHookListenerProps) {
    const [hotkeysOptions, setHotkeysOptions] = useState({
        enabled: enableHotkeys,
        scopes
    });

    useHotkeys(
        'enter',
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
            addBlock();
        },
        hotkeysOptions
    );

    useHotkeys(
        'escape',
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['up', 'down', 'left', 'right'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+z', 'meta+z'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+y', 'meta+y'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+0', 'meta+alt+0'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+1', 'meta+alt+1'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+2', 'meta+alt+2'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+3', 'meta+alt+3'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+4', 'meta+alt+4'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+5', 'meta+alt+5'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+6', 'meta+alt+6'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+7', 'meta+alt+7'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+8', 'meta+alt+8'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+9', 'meta+alt+9'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['shift+up', 'shift+down'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['backspace', 'delete'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+d', 'meta+d'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+slash', 'meta+slash'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    useHotkeys(
        ['ctrl+shift+up', 'ctrl+shift+down', 'ctrl+shift+left', 'ctrl+shift+right', 'meta+shift+up', 'meta+shift+down', 'meta+shift+left', 'meta+shift+right'],
        (keyboardEvent: KeyboardEvent) => {
            keyboardEvent.preventDefault();
        },
        hotkeysOptions
    );

    return <>{children}</>;
}
