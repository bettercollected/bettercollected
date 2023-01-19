import { createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

export interface BrandColor {
    primary_color: string;
    accent_color: string;
    text_color: string;
}

export interface WorkspaceState {
    bannerImage?: string;
    customDomain: string;
    description: string;
    id: string;
    mailSettings: string | null;
    ownerId: string;
    privacy_profile_url: string;
    profileImage?: string;
    terms_of_service_url: string;
    theme: BrandColor;
    title: string;
    workspaceName: string;
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
    privacy_profile_url: '',
    profileImage: '',
    terms_of_service_url: '',
    theme: {
        primary_color: '',
        accent_color: '',
        text_color: ''
    }
};

export const slice = createSlice({
    name: 'workspace',
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
        storage,
        whitelist: ['value']
    },
    slice.reducer
);

const reducerObj = { reducerPath: slice.name, reducer: workspaceReducer };

// Action creators are generated for each case reducer function
export const { setWorkspace } = slice.actions;

export default reducerObj;
