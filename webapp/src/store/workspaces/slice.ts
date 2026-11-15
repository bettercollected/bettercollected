import { FormTheme } from '@app/constants/theme';
import type { AppTheme } from '@app/lib/app-theme';
import { createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

import { RootState } from '@app/store/store';

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
    privacy_policy_url: string;
    profileImage?: string;
    terms_of_service_url: string;
    theme: BrandColor;
    title: string;
    workspaceName: string;
    isPro: boolean;
    customDomainVerified?: boolean;
    // Saved custom form themes (workspace "brand kit" palettes).
    customThemes?: FormTheme[];
    // The look of the staff dashboard (members only, see models/dtos/workspace-dto.ts).
    appTheme?: AppTheme;
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
    theme: {
        primary_color: '',
        accent_color: '',
        text_color: ''
    },
    isPro: false
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
            // Most answers that replace the workspace (a rename, a logo, the saved themes) do not carry the app
            // theme, which only the dashboard's own lookup sends: the one this workspace has stays.
            const keep = action.payload?.appTheme === undefined && action.payload?.id && action.payload.id === state.id ? state.appTheme : undefined;
            return { ...action.payload, ...(keep ? { appTheme: keep } : {}) };
        },
        // The app theme was changed (the Appearance card): the answer of the server for this workspace.
        setAppTheme: (state, action: { payload: { workspaceId: string; appTheme: AppTheme } }) => {
            if (state.id === action.payload.workspaceId) state.appTheme = action.payload.appTheme;
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
export const { setWorkspace, setAppTheme } = slice.actions;

export const selectWorkspace = (state: RootState) => state.workspace;
export default reducerObj;
