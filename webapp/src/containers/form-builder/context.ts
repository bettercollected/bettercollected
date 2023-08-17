import React from 'react';

import { atom, useAtom } from 'jotai';

const formBuilderAtom = atom({ backspaceCount: 0 });

export default function useFormBuilderState() {
    const [state, setState] = useAtom(formBuilderAtom);

    const setBackspaceCount = (count: number) => {
        setState({ ...state, backspaceCount: count });
    };
    return { ...state, setBackspaceCount };
}
