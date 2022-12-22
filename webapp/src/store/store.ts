import { Reducer, combineReducers, configureStore } from '@reduxjs/toolkit';
import { setupListeners } from '@reduxjs/toolkit/query';
import { createLogger } from 'redux-logger';
import { persistStore } from 'redux-persist';

import environments from '@app/configs/environments';
import { RESET_STATE_ACTION_TYPE } from '@app/store/actions/resetState';
import workspaceSlice from '@app/store/workspaces/slice';

import { authApi } from './auth/api';
import searchReducerObj, { searchSlice } from './search/searchSlice';
import { workspacesApi } from './workspaces/api';

const loggerMiddleware = createLogger();

// Add more middlewares here
const middlewares = [authApi.middleware, workspacesApi.middleware];

// if (environments.IS_IN_PRODUCTION_MODE) middlewaress.splice(0, 1);

const reducers = {
    [workspaceSlice.reducerPath]: workspaceSlice.reducer,
    [searchReducerObj.reducerPath]: searchSlice.reducer,
    [authApi.reducerPath]: authApi.reducer,
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
