export const reorder = (list: Array<any>, startIndex: number, endIndex: number) => {
    const result = Array.from(list);
    const [removed] = result.splice(startIndex - 1, 1);
    result.splice(endIndex - 1, 0, removed);
    return result;
};
