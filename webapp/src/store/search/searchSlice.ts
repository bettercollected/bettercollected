import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

export interface SearchState {
    activeSearchContent: Array<any>;
    searchInput: String;
}

const initialState: SearchState = {
    activeSearchContent: [],
    searchInput: ''
};

export const searchSlice = createSlice({
    name: 'search',
    initialState,
    reducers: {
        setActiveData: (state, action: PayloadAction<any>) => {
            state.activeSearchContent = action.payload;
        },
        setSearchInput: (state, action: PayloadAction<any>) => {
            state.searchInput = action.payload;
        }
    }
});

const searchReducer = persistReducer(
    {
        key: 'rtk:searchData',
        storage,
        whitelist: ['activeSearchContent', 'searchInput']
    },
    searchSlice.reducer
);

const searchReducerObj = { reducerPath: searchSlice.name, reducer: searchReducer };

// Action creators are generated for each case reducer function
export const { setActiveData, setSearchInput } = searchSlice.actions;

export default searchReducerObj;
