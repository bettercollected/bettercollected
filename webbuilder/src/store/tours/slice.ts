import { PayloadAction, createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

import { JoyrideStateWithoutSteps } from '@app/models/dtos/joyride';

interface JoyrideSliceState {
    joyrides: Record<string, JoyrideStateWithoutSteps>;
    isAnyJoyrideRunning: boolean;
}

const initialState: JoyrideSliceState = {
    joyrides: {},
    isAnyJoyrideRunning: false
};

const joyrideSlice = createSlice({
    name: 'joyride',
    initialState,
    reducers: {
        startJoyride: (state, action: PayloadAction<string>) => {
            state.joyrides[action.payload].run = true;
            state.isAnyJoyrideRunning = true;
        },
        finishJoyride: (state, action: PayloadAction<string>) => {
            state.joyrides[action.payload].finished = true;
            state.joyrides[action.payload].run = false;

            const isAnyRunning = Object.values(state.joyrides).some(
                (joyride) => joyride.run
            );
            state.isAnyJoyrideRunning = isAnyRunning;
        },
        setJoyrideState: (state, action: PayloadAction<JoyrideStateWithoutSteps>) => {
            const { id, ...joyrideState } = action.payload;
            // @ts-ignore
            state.joyrides[id] = joyrideState;

            const isAnyRunning = Object.values(state.joyrides).some(
                (joyride) => joyride.run
            );
            state.isAnyJoyrideRunning = isAnyRunning;
        }
    }
});

const joyrideStateReducer = persistReducer(
    {
        key: 'rtk:joyride',
        storage
    },
    joyrideSlice.reducer
);

export const { startJoyride, finishJoyride, setJoyrideState } = joyrideSlice.actions;

const reducerObj = {
    reducerPath: joyrideSlice.name,
    reducer: joyrideStateReducer,
    initialState
};

export default reducerObj;
