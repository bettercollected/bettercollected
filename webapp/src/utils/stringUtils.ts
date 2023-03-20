import { isNetherUndefinedNorNull } from '@app/utils/validationUtils';

export const shortenStr = (str: string | number, expectedLength?: number, firstIndex = 0) => {
    if (isNetherUndefinedNorNull(expectedLength)) {
        return str.toString().substr(firstIndex, expectedLength);
    }
    return str;
};

export const toMidDottedStr = (str: string | number, leadingVisible = 12, firstIndex = 0) => {
    if (!str) return str;
    const total = str.toString().length;
    if (total <= leadingVisible * 2) return str;
    const leadingStr = str.toString().substring(firstIndex, leadingVisible);
    const trailingStr = str.toString().substring(total - leadingVisible);
    return `${leadingStr}...${trailingStr}`;
};

export const toEndDottedStr = (str: string | number, leadingVisible = 12, firstIndex = 0) => {
    if (!str) return str;
    if (str.toString().length <= leadingVisible) return str.toString();
    const leadingStr = str.toString().substring(firstIndex, leadingVisible);
    return `${leadingStr}...`;
};

export const capitalize = (val: { toString: () => string }): string => {
    if (!val) return '';
    const firstChar = val.toString()[0]?.toUpperCase();
    return `${firstChar}${val.toString().substring(1).toLowerCase()}`;
};
