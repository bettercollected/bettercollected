import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

export interface FormsState {
    formsArray: Array<any>;
}

const initialState: FormsState = {
    formsArray: []
};

export const activeTabDataSlice = createSlice({
    name: 'activeData',
    initialState,
    reducers: {
        // increment: (state) => {
        //     // Redux Toolkit allows us to write "mutating" logic in reducers. It
        //     // doesn't actually mutate the state because it uses the Immer library,
        //     // which detects changes to a "draft state" and produces a brand new
        //     // immutable state based off those changes
        //     state.f += 1;
        // },
        // decrement: (state) => {
        //     state.value -= 1;
        // },
        setActiveData: (state, action: PayloadAction<any>) => {
            state.formsArray = action.payload;
        }
        // getActiveData: (state) => {
        //     return state.formsArray
        // }
    }
});

const activeTabDataReducer = persistReducer(
    {
        key: 'rtk:activeTabData',
        storage,
        whitelist: ['formsArray']
    },
    activeTabDataSlice.reducer
);

const activeDataReducerObj = { reducerPath: activeTabDataSlice.name, reducer: activeTabDataReducer };

// Action creators are generated for each case reducer function
export const { setActiveData } = activeTabDataSlice.actions;

export default activeDataReducerObj;
