import { createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

export interface WorkspaceState {
    bannerImage?: string;
    customDomain: string;
    description: string;
    id: string;
    mailSettings: string | null;
    ownerId: string;
    privacy_policy_url: string;
    profileImage?: string;
    terms_of_service_url: string;
    title: string;
    workspaceName: string;
    isPro: boolean;
}

const initialState: WorkspaceState = {
    workspaceName: '',
    id: '',
    title: '',
    description: '',
    customDomain: '',
    bannerImage: '',
    mailSettings: '',
    ownerId: '',
    privacy_policy_url: '',
    profileImage: '',
    terms_of_service_url: '',
    isPro: false
};

export const slice = createSlice({
    name: 'workspaceV2',
    initialState,
    reducers: {
        setWorkspace: (state, action) => {
            // Redux Toolkit allows us to write "mutating" logic in reducers. It
            // doesn't actually mutate the state because it uses the Immer library,
            // which detects changes to a "draft state" and produces a brand new
            // immutable state based off those changes;
            return { ...action.payload };
        }
    }
});

const workspaceReducer = persistReducer(
    {
        key: 'rtk:workspace',
        storage
    },
    slice.reducer
);

export const { setWorkspace } = slice.actions;

const reducerObj = { reducerPath: slice.name, reducer: workspaceReducer };

export default reducerObj;
