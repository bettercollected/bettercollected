import { Reducer, combineReducers, configureStore } from '@reduxjs/toolkit';
import { setupListeners } from '@reduxjs/toolkit/query';
import { createLogger } from 'redux-logger';
import { persistStore } from 'redux-persist';

import environments from '@app/configs/environments';
import { RESET_STATE_ACTION_TYPE } from '@app/store/actions/resetState';
import { authApi } from '@app/store/auth/api';
import authSlice from '@app/store/auth/slice';
import fillFormSlice from '@app/store/fill-form/slice';
import builder from '@app/store/form-builder/builderSlice';
import formSlice from '@app/store/forms/slice';
import { plansApi } from '@app/store/plans/api';
import { providerApi } from '@app/store/providers/api';
import joyrideSlice from '@app/store/tours/slice';
import { workspacesApi } from '@app/store/workspaces/api';
import { membersNInvitationsApi } from '@app/store/workspaces/members-n-invitations-api';
import workspaceSlice from '@app/store/workspaces/slice';

// Add more middlewares here
// const middlewares = [loggerMiddleware, authApi.middleware, membersNInvitationsApi.middleware, plansApi.middleware, providerApi.middleware, workspacesApi.middleware];
const middlewares = [authApi.middleware, membersNInvitationsApi.middleware, plansApi.middleware, providerApi.middleware, workspacesApi.middleware];

// if (environments.IS_IN_PRODUCTION_MODE) middlewares.splice(0, 1);

const reducers = {
    [authSlice.reducerPath]: authSlice.reducer,
    [formSlice.reducerPath]: formSlice.reducer,
    [joyrideSlice.reducerPath]: joyrideSlice.reducer,
    [workspaceSlice.reducerPath]: workspaceSlice.reducer,
    [builder.reducerPath]: builder.reducer,
    [fillFormSlice.reducerPath]: fillFormSlice.reducer,
    [authApi.reducerPath]: authApi.reducer,
    [membersNInvitationsApi.reducerPath]: membersNInvitationsApi.reducer,
    [providerApi.reducerPath]: providerApi.reducer,
    [plansApi.reducerPath]: plansApi.reducer,
    [workspacesApi.reducerPath]: workspacesApi.reducer
};

const combinedReducer = combineReducers<typeof reducers>(reducers);

export const rootReducer: Reducer<RootState> = (state, action) => {
    if (action.type === RESET_STATE_ACTION_TYPE) {
        state = {} as RootState;
    }

    return combinedReducer(state, action);
};

export const store = configureStore({
    reducer: rootReducer,
    middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware({
            serializableCheck: false
            // serializableCheck: {
            //     ignoredActions: [
            //         FLUSH,
            //         REHYDRATE,
            //         PAUSE,
            //         PERSIST,
            //         PURGE,
            //         REGISTER,
            //     ]
            // }
        }).concat(middlewares),
    preloadedState: {},
    devTools: !environments.IS_IN_PRODUCTION_MODE
    // enhancers: environments.IS_IN_PRODUCTION_MODE ? [] : [monitorReducerEnhancer]
});

export const persistor = persistStore(store);

export type AppDispatch = typeof store.dispatch;
export type RootState = ReturnType<typeof combinedReducer>;

setupListeners(store.dispatch);
