import { TypedUseSelectorHook, useDispatch, useSelector } from 'react-redux';

import type { AppDispatch, RootState } from '@app/store/store';

// Use throughout your app instead of plain `useDispatch` and `useSelector`
export const useAppDispatch = () => useDispatch<AppDispatch>();
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;

export const useAppAsyncDispatch = () => {
    const dispatch: AppDispatch = useAppDispatch();

    const asyncDispatch = async (action: any) => {
        if (typeof action === 'function') {
            return Promise.resolve(action(dispatch));
        }

        return Promise.resolve(dispatch(action));
    };

    return asyncDispatch;
};
