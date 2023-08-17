import { useMemo } from 'react';

import { debounce } from 'lodash';

import { setTyping } from '@app/store/form-builder/actions';
import { useAppDispatch } from '@app/store/hooks';

export default function useUserTypingDetection() {
    const dispatch = useAppDispatch();
    const handleUserTypingEnd = useMemo(() => {
        return debounce(() => {
            dispatch(setTyping(false));
        }, 500);
    }, [dispatch]);

    return { handleUserTypingEnd };
}
