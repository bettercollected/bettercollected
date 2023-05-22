import { createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

import { JoyrideState } from '@app/models/dtos/joyride';
import { RootState } from '@app/store/store';

export const initialTourState: JoyrideState = {
    id: '',
    finished: false,
    steps: []
};

export const slice = createSlice({
    name: 'joyride',
    initialState: {},
    reducers: {
        setJoyrideState: (state, action) => {
            return { ...state, ...action.payload };
        }
    }
});

const joyrideStateReducer = persistReducer(
    {
        key: 'rtk:joyride',
        storage,
        whitelist: ['value']
    },
    slice.reducer
);

const reducerObj = { reducerPath: slice.name, reducer: joyrideStateReducer };

export const selectJoyrideState = (state: RootState) => state.joyride;
export const { setJoyrideState } = slice.actions;

export default reducerObj;
