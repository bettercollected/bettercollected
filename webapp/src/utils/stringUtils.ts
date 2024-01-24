import { isNetherUndefinedNorNull } from '@app/utils/validationUtils';

export const shortenStr = (str: string | number, expectedLength?: number, firstIndex = 0) => {
    if (isNetherUndefinedNorNull(expectedLength)) {
        return str.toString().substr(firstIndex, expectedLength);
    }
    return str;
};

export const isEmptyString = (str: string) => {
    return str.length === 0;
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
    if (!str) return '';
    if (str.toString().length <= leadingVisible) return str.toString();
    const leadingStr = str.toString().substring(firstIndex, leadingVisible);
    return `${leadingStr}...`;
};

export const capitalize = (val: { toString: () => string }): string => {
    if (!val) return '';
    const firstChar = val.toString()[0]?.toUpperCase();
    return `${firstChar}${val.toString().substring(1).toLowerCase()}`;
};

export const ellipsesText = (text: string, limit: number) => {
    let descStripped = text;
    if (text.length > limit) {
        descStripped = toEndDottedStr(text, limit);
    }

    return descStripped.replace(/\\n/gi, '\n');
};

export const trimTooltipTitle = (title?: string, limit: number = 20) => {
    if (title && title.length > limit) return title;
    return '';
};

export const getLastItem = (arr: string) => {
    return arr.charAt(arr.length - 1);
};