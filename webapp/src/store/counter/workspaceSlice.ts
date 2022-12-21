import { createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

export interface WorkspaceState {
    workspaceName: string;
    workspaceId: string;
}

const initialState: WorkspaceState = {
    workspaceName: '',
    workspaceId: ''
};

export const workspaceSlice = createSlice({
    name: 'workspace',
    initialState,
    reducers: {
        setWorkspace: (state, action) => {
            // Redux Toolkit allows us to write "mutating" logic in reducers. It
            // doesn't actually mutate the state because it uses the Immer library,
            // which detects changes to a "draft state" and produces a brand new
            // immutable state based off those changes;
            state.workspaceId = action.payload?.workspaceId || '';
            state.workspaceName = action.payload?.workspaceName || '';
        }
    }
});

const workspaceReducer = persistReducer(
    {
        key: 'rtk:workspace',
        storage,
        whitelist: ['value']
    },
    workspaceSlice.reducer
);

const reducerObj = { reducerPath: workspaceSlice.name, reducer: workspaceReducer };

// Action creators are generated for each case reducer function
export const { setWorkspace } = workspaceSlice.actions;

export default reducerObj;
