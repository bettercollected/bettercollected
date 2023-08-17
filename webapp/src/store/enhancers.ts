const round = (number: number) => Math.round(number * 100) / 100;

const consoleStyle = ['color: #ffffff', 'background: #6366f1', 'font-size: 12px', 'padding: 10px', 'width: 100%', 'font-weight: bold'].join(';');

export const monitorReducerEnhancer: any =
    (createStore: any): any =>
    (reducer: any, initialState: any, enhancer: any): any => {
        const monitoredReducer = (state: any, action: any) => {
            const start = performance.now();
            const newState = reducer(state, action);
            const end = performance.now();
            const diff = round(end - start);

            // console.log(`%c${action.type} Reducer process time ${diff} seconds`, consoleStyle);

            return newState;
        };

        return createStore(monitoredReducer, initialState, enhancer);
    };
