import { createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

const statusSlice = createSlice({
    name: 'mutationStatus',
    initialState: {
        patchTemplate: 'idle',
        publishForm: 'idle'
    },
    reducers: {
        updateStatus: (state, action) => {
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

const reducerObj = { reducer: statusReducer, reducerPath: 'mutationStatus' };

export default reducerObj;
