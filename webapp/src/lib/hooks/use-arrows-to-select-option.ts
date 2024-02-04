import { useEffect } from 'react';

import { KeyType } from '@app/models/enums/formBuilder';


export default function useArrowsToSelectOption(handleSelect: any, handleNext: any, handlePrevious: any) {
    useEffect(() => {
        const handleKeyDown = (e: any) => {
            const keyActions: any = {
                [KeyType.Enter]: () => {
                    e.preventDefault();
                    e.stopPropagation();
                    handleSelect();
                },
                [KeyType.ArrowDown]: () => {
                    e.preventDefault();
                    e.stopPropagation();
                    handleNext(e);
                },
                [KeyType.ArrowUp]: () => {
                    e.preventDefault();
                    e.stopPropagation();
                    handlePrevious(e);
                },
                default: () => {}
            };

            const action = keyActions[e.key] || keyActions.default;
            action();
        };

        document.addEventListener('keydown', handleKeyDown);

        return () => {
            document.removeEventListener('keydown', handleKeyDown);
        };
    }, [handlePrevious, handleSelect, handleNext]);
}