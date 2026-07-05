export function deepCopy<T>(obj: T): T {
    if (typeof obj !== 'object' || obj === null) {
        return obj as T;
    }

    if (Array.isArray(obj)) {
        return obj.map(deepCopy) as unknown as T;
    }

    const copiedObj = {} as T;
    for (const [key, value] of Object.entries(obj)) {
        (copiedObj as any)[key] = deepCopy(value);
    }
    return copiedObj;
}
