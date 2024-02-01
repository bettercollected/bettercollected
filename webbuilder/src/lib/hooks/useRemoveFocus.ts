import { useCallback, useEffect, useState } from 'react';

function useRemoveFocus(size: number) {
    const [currentFocus, setCurrentFocus] = useState(0);

    const handleKeyDown = useCallback(
        (e: any) => {
            if (e.keyCode === 40) {
                // Down arrow
                e.preventDefault();
                setCurrentFocus(currentFocus === size - 1 ? 0 : currentFocus + 1);
            } else if (e.keyCode === 38) {
                // Up arrow
                e.preventDefault();
                setCurrentFocus(currentFocus === 0 ? size - 1 : currentFocus - 1);
            }
        },
        [size, currentFocus, setCurrentFocus]
    );

    useEffect(() => {
        document.addEventListener('keydown', handleKeyDown, false);
        return () => {
            document.removeEventListener('keydown', handleKeyDown, false);
        };
    }, [handleKeyDown]);

    return [currentFocus, setCurrentFocus];
}

export default useRemoveFocus;
