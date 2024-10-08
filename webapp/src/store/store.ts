import { combineReducers, configureStore, Reducer } from '@reduxjs/toolkit';
import { setupListeners } from '@reduxjs/toolkit/query';
import { persistStore } from 'redux-persist';

import environments from '@app/configs/environments';
import { RESET_STATE_ACTION_TYPE } from '@app/store/actions/resetState';
import { authApi } from '@app/store/auth/api';
import authSlice from '@app/store/auth/slice';
import { couponCodeApi } from '@app/store/coupon-code/api';
import fillFormSlice from '@app/store/fill-form/slice';
import builder from '@app/store/form-builder/builderSlice';
import formSlice from '@app/store/forms/slice';
import { plansApi } from '@app/store/plans/api';
import { providerApi } from '@app/store/providers/api';
import { templateApi } from '@app/store/template/api';
import joyrideSlice from '@app/store/tours/slice';
import { workspacesApi } from '@app/store/workspaces/api';
import { membersNInvitationsApi } from '@app/store/workspaces/members-n-invitations-api';
import workspaceSlice from '@app/store/workspaces/slice';

import { apiActionsApi } from './api-actions-api';
import { consentApi } from './consent/api';
import consentSlice from './consent/consentSlice';
import mutationStatusSlice from './mutations/slice';
import { priceSuggestionApi } from './price-suggestion/api';

import { templatesApi } from '@app/store/redux/templateApi';
import { integrationApi } from '@app/store/integrationApi';

import { formsApi } from '@app/store/redux/formApi';
import { importApi } from '@app/store/redux/importApi';
import { mediaLibraryApi } from './media-library/api';
import { analyticsApi } from './analytics/api';
// Add more middlewares here
// const middlewares = [loggerMiddleware, authApi.middleware, membersNInvitationsApi.middleware, plansApi.middleware, providerApi.middleware, workspacesApi.middleware];
const middlewares = [
    priceSuggestionApi.middleware,
    authApi.middleware,
    membersNInvitationsApi.middleware,
    plansApi.middleware,
    providerApi.middleware,
    workspacesApi.middleware,
    consentApi.middleware,
    templateApi.middleware,
    apiActionsApi.middleware,
    couponCodeApi.middleware,
    formsApi.middleware,
    templatesApi.middleware,
    importApi.middleware,
    mediaLibraryApi.middleware,
    analyticsApi.middleware,
    integrationApi.middleware
];

// if (environments.IS_IN_PRODUCTION_MODE) middlewares.splice(0, 1);

const reducers = {
    [mutationStatusSlice.reducerPath]: mutationStatusSlice.reducer,
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
    [workspacesApi.reducerPath]: workspacesApi.reducer,
    [apiActionsApi.reducerPath]: apiActionsApi.reducer,
    [consentSlice.reducerPath]: consentSlice.reducer,
    [consentApi.reducerPath]: consentApi.reducer,
    [templateApi.reducerPath]: templateApi.reducer,
    [couponCodeApi.reducerPath]: couponCodeApi.reducer,
    [priceSuggestionApi.reducerPath]: priceSuggestionApi.reducer,
    [mutationStatusSlice.reducerPath]: mutationStatusSlice.reducer,
    [formsApi.reducerPath]: formsApi.reducer,
    [templatesApi.reducerPath]: templatesApi.reducer,
    [importApi.reducerPath]: importApi.reducer,
    [mediaLibraryApi.reducerPath]: mediaLibraryApi.reducer,
    [analyticsApi.reducerPath]: analyticsApi.reducer,
    [integrationApi.reducerPath]: integrationApi.reducer
    // Add more reducers here
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
        }).concat(middlewares),
    preloadedState: {},
    devTools: !environments.IS_IN_PRODUCTION_MODE
});

export const persistor = persistStore(store);

export type AppDispatch = typeof store.dispatch;
export type RootState = ReturnType<typeof combinedReducer>;

setupListeners(store.dispatch);
