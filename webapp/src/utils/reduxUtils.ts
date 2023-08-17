export function convertProxyToObject<T>(proxyObj: T): T {
    const newObj: any = {};

    if (proxyObj) {
        Object.getOwnPropertyNames(proxyObj).forEach((key) => {
            // @ts-ignore
            newObj[key] = proxyObj[key];
        });
    }

    return newObj;
}
