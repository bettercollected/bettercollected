import { RefObject, useEffect, useState } from 'react';

export default function useIsOverflow(
    ref: RefObject<HTMLElement | null>,
    callback?: (overflow: boolean) => void
) {
    const [isOverflow, setIsOverflow] = useState(false);

    useEffect(() => {
        const checkOverflow = () => {
            if (ref.current) {
                const hasOverflow = ref.current.scrollHeight > ref.current.clientHeight;
                setIsOverflow(hasOverflow);
                callback?.(hasOverflow);
            }
        };

        // Check initial overflow
        checkOverflow();

        // Create a MutationObserver to monitor changes to the content
        const observer = new MutationObserver(checkOverflow);

        if (ref.current) {
            observer.observe(ref.current, {
                childList: true, // Observe changes to the child nodes
                subtree: true // Observe changes in the entire subtree of the element
            });
        }

        return () => {
            observer.disconnect(); // Clean up the observer on unmount
        };
    }, [callback, ref]);

    return isOverflow;
}
