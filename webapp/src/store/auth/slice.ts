import { createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

import { Plan, UserStatus } from '@app/models/dtos/UserStatus';
import { RootState } from '@app/store/store';

export const initialAuthState: UserStatus = {
    email: '',
    plan: Plan.FREE,
    roles: [],
    id: '',
    isAdmin: false,
    isLoading: true
};

export const slice = createSlice({
    name: 'auth',
    initialState: initialAuthState,
    reducers: {
        setAuth: (state, action) => {
            return { ...state, ...action.payload };
        }
    }
});

const authReducer = persistReducer(
    {
        key: 'rtk:auth',
        storage,
        whitelist: ['value']
    },
    slice.reducer
);

const reducerObj = {
    reducerPath: slice.name,
    reducer: authReducer
};

export const { setAuth } = slice.actions;

export default reducerObj;

export const selectAuth = (state: any) => state.auth;

export const selectIsAdmin = (state: any) => state.auth.isAdmin;

export const selectIsProPlan = (state: RootState) => !!state.workspace.isPro;
