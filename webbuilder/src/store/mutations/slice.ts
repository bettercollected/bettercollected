import { PayloadAction, createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

interface MutationStatusState {
    patchTemplate: string;
    publishForm: string;
}

const initialState: MutationStatusState = {
    patchTemplate: 'idle',
    publishForm: 'idle'
};

const statusSlice = createSlice({
    name: 'mutationStatus',
    initialState,
    reducers: {
        updateStatus: (
            state,
            action: PayloadAction<{ endpoint: string; status: string }>
        ) => {
            return {
                ...state,
                [action.payload.endpoint]: action.payload.status
            };
        }
    }
});

const statusReducer = persistReducer(
    {
        key: 'rtk:mutationStatus',
        storage
    },
    statusSlice.reducer
);

export const { updateStatus } = statusSlice.actions;

const reducerObj = {
    reducer: statusReducer,
    reducerPath: statusSlice.name,
    initialState
};

export default reducerObj;
