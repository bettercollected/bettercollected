export const throttle = (func: Function, delay: number) => {
    let timeoutId: any;
    return (...args: any[]) => {
        if (!timeoutId) {
            timeoutId = setTimeout(() => {
                // @ts-ignore
                func.apply(this, args);
                timeoutId = null;
            }, delay);
        }
    };
};
