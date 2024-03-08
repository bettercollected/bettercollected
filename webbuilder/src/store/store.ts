import { Reducer, combineReducers, configureStore } from '@reduxjs/toolkit';
import { setupListeners } from '@reduxjs/toolkit/query';
import { createLogger } from 'redux-logger';
import { persistStore } from 'redux-persist';

import environments from '@app/configs/environments';
import { RESET_STATE_ACTION_TYPE } from '@app/store/actions/resetState';
import mutationStatusSlice from '@app/store/mutations/slice';
import workspaceSlice from '@app/store/redux/workspace';
import joyrideSlice from '@app/store/tours/slice';

import { formsApi } from './redux/formApi';

// Add more middlewares here
const loggerMiddleware = createLogger({ collapsed: true });
const middlewares: any = [loggerMiddleware, formsApi.middleware];

if (
    environments.IS_IN_PRODUCTION_MODE ||
    environments.IS_REDUX_LOGGER_DISABLED ||
    environments.NEXT_PUBLIC_NODE_ENV === 'production'
)
    middlewares.splice(0, 1);

const reducers = {
    [mutationStatusSlice.reducerPath]: mutationStatusSlice.reducer,
    [joyrideSlice.reducerPath]: joyrideSlice.reducer,
    [workspaceSlice.reducerPath]: workspaceSlice.reducer,
    [formsApi.reducerPath]: formsApi.reducer
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
    // preloadedState: {
    // [mutationStatusSlice.reducerPath.toString()]: mutationStatusSlice.initialState,
    // [joyrideSlice.reducerPath.toString()]: joyrideSlice.initialState
    // },
    devTools: !environments.IS_IN_PRODUCTION_MODE,
    enhancers: (getDefaultEnhancers) =>
        getDefaultEnhancers().concat(
            environments.IS_IN_PRODUCTION_MODE || environments.IS_REDUX_LOGGER_DISABLED
                ? []
                : []
        )
});

export const persistor = persistStore(store);

export type AppDispatch = typeof store.dispatch;
export type RootState = ReturnType<typeof combinedReducer>;

setupListeners(store.dispatch);
