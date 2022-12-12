import { useEffect } from 'react';

/**
 * Custom hook to close the dropdown when clicked outside of the dropdown div
 * @param ref
 * @param callback
 * @param modalStatus
 */
const useOutsideClick = (ref: any, callback: any, modalStatus: any) => {
    const handleClick = (e: any) => {
        if (ref.current && !(ref.current === e.target) && modalStatus) {
            callback();
        } else {
            return;
        }
    };

    useEffect(() => {
        document.addEventListener('click', handleClick);

        return () => {
            document.removeEventListener('click', handleClick);
        };
    });
};

export default useOutsideClick;
