import { useEffect } from 'react';

import { resetBuilderMenuState } from '@app/store/form-builder/actions';
import { useAppDispatch } from '@app/store/hooks';

const useClickOutsideMenu = (divId: string): void => {
    const dispatch = useAppDispatch();
    useEffect(() => {
        const onClick = (event: MouseEvent) => {
            const element = event.target as HTMLElement;
            if (!element.closest(`#${divId}`)) {
                dispatch(resetBuilderMenuState());
            }
        };

        document.addEventListener('click', onClick);
        return () => {
            document.removeEventListener('click', onClick);
        };
    }, [divId]);
};

export default useClickOutsideMenu;
