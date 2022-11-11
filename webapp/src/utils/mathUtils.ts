export function intDiv(a: number, b: number) {
    return Math.floor(a / b);
}

export const thousandValue = (value: number) => value * 10 ** -3;

export const millionValue = (value: number) => value * 10 ** -6;

export const billionValue = (value: number) => value * 10 ** -9;

export const trillionValue = (value: number) => value * 10 ** -12;

export const isInThousandRange = (value: number) => value >= 10 ** 3 && value < 10 ** 6;

export const isInMillionRange = (value: number) => value >= 10 ** 6 && value < 10 ** 9;

export const isInBillionRange = (value: number) => value >= 10 ** 9 && value < 10 ** 12;

export const isInTrillionRange = (value: number) => value >= 10 ** 12 && value < 10 ** 15;

export const getDecimalPlaceValues = (value: number, fixedValue: number = 2) => (value % 1 === 0 ? value : value.toFixed(fixedValue));
