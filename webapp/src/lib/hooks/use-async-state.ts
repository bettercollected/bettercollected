import { useCallback, useEffect, useRef, useState } from 'react';

function useAsyncState<T>(initialState: T): [T, (newState: T) => Promise<void>] {
    const [state, setState] = useState<T>(initialState);
    const resolveState = useRef<((value: T | PromiseLike<T>) => void) | null | undefined>();
    const isMounted = useRef(false);

    useEffect(() => {
        isMounted.current = true;

        return () => {
            isMounted.current = false;
        };
    }, []);

    useEffect(() => {
        if (resolveState.current) {
            // @ts-ignore
            resolveState.current(state);
        }
    }, [state]);

    const setAsyncState = useCallback(
        (newState: T) =>
            new Promise<void>((resolve) => {
                if (isMounted.current) {
                    // @ts-ignore
                    resolveState.current = resolve;
                    setState(newState);
                }
            }),
        []
    );

    return [state, setAsyncState];
}

export default useAsyncState;