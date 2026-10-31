import { readFileSync } from 'fs';
import { resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { AMOUNT_MAX_INTEGER_DIGITS, CURRENCIES_MAX, CURRENCY_DECIMALS, amountFromInput, currencyDecimals, currencyExportText, formatAmount, isCurrencyCode, parseAmount } from './currency';
import { isIsoDate } from './iso-date';
import { isTime, minutesOf } from './time-of-day';

const shared = JSON.parse(readFileSync(resolve(__dirname, '../../../docs/spec/currencies-v1.json'), 'utf8'));

describe('the currency table', () => {
    it('is the shared one, the same as the server reads', () => {
        expect({ ...CURRENCY_DECIMALS }).toEqual(shared.decimals);
        expect(CURRENCIES_MAX).toBe(shared.maxCurrencies);
        expect(AMOUNT_MAX_INTEGER_DIGITS).toBe(shared.maxIntegerDigits);
    });

    it('knows codes and decimals', () => {
        expect(isCurrencyCode('EUR') && isCurrencyCode('JPY')).toBe(true);
        expect(isCurrencyCode('eur') || isCurrencyCode('XXX') || isCurrencyCode(undefined) || isCurrencyCode(978)).toBe(false);
        expect(['EUR', 'JPY', 'KWD', '???'].map(currencyDecimals)).toEqual([2, 0, 3, 2]);
    });
});

describe('parseAmount', () => {
    it.each([
        ['12.50', 'EUR', 12.5],
        ['12', 'EUR', 12],
        ['0', 'EUR', 0],
        ['0.05', 'EUR', 0.05],
        ['-5', 'EUR', -5],
        ['1000', 'JPY', 1000],
        ['1.234', 'KWD', 1.234],
        ['12.505', undefined, 12.505]
    ])('reads %s in %s', (amount, code, expected) => {
        expect(parseAmount(amount, code)).toBe(expected);
    });

    it.each([
        ['12,50', 'EUR'],
        ['12.505', 'EUR'],
        ['100.5', 'JPY'],
        ['1,250.00', 'EUR'],
        ['1e3', 'EUR'],
        ['+5', 'EUR'],
        ['007', 'EUR'],
        ['-', 'EUR'],
        ['12.', 'EUR'],
        ['.5', 'EUR'],
        [' 12', 'EUR'],
        ['12\n', 'EUR'],
        ['', 'EUR'],
        ['NaN', 'EUR'],
        ['1'.padEnd(AMOUNT_MAX_INTEGER_DIGITS + 1, '0'), 'EUR'],
        [12, 'EUR'],
        [undefined, 'EUR']
    ])('refuses %s in %s', (amount, code) => {
        expect(parseAmount(amount, code as string)).toBeUndefined();
    });
});

describe('amountFromInput', () => {
    it('reads a comma or a dot as the decimal separator and nothing else', () => {
        expect(amountFromInput('12,50', 'EUR')).toBe('12.50');
        expect(amountFromInput(' 12.5 ', 'EUR')).toBe('12.5');
        expect(amountFromInput('1.250,00', 'EUR')).toBeUndefined();
        expect(amountFromInput('', 'EUR')).toBeUndefined();
        expect(amountFromInput('12,505', 'EUR')).toBeUndefined();
    });
});

describe('displaying an amount', () => {
    it('is written the way the form language writes it', () => {
        expect(formatAmount({ code: 'EUR', amount: '12.5' }, 'nl').replace(/\s/g, ' ')).toBe('€ 12,50');
        expect(formatAmount({ code: 'EUR', amount: '12.5' }, 'en')).toBe('€12.50');
        expect(formatAmount({ code: 'JPY', amount: '1500' }, 'en')).toContain('1,500');
    });

    it('falls back to the stored text for what is not an amount, and to nothing when there is none', () => {
        expect(formatAmount({ code: 'EUR', amount: '12,5' })).toBe('EUR 12,5');
        expect(formatAmount({ code: 'EUR' })).toBe('');
        expect(formatAmount(undefined)).toBe('');
    });

    it('is one stable text in the export: code, space, dot decimal', () => {
        expect(currencyExportText({ code: 'GBP', amount: '250.50' })).toBe('GBP 250.50');
        expect(currencyExportText({ code: 'GBP', amount: '' })).toBe('');
        expect(currencyExportText(undefined)).toBe('');
    });
});

describe('minus zero', () => {
    it('is no amount: zero has one writing', () => {
        for (const text of ['-0', '-0.0', '-0.00', '-0.000']) expect(parseAmount(text)).toBeUndefined();
        expect(parseAmount('0')).toBe(0);
        expect(parseAmount('0.00', 'EUR')).toBe(0);
        expect(parseAmount('-0.01', 'EUR')).toBe(-0.01);
    });

    it('is typed as zero: the input is stored without its minus', () => {
        expect(amountFromInput('-0', 'EUR')).toBe('0');
        expect(amountFromInput('-0,00', 'EUR')).toBe('0.00');
        expect(amountFromInput(' -0.0 ', 'EUR')).toBe('0.0');
        expect(amountFromInput('-0.001', 'EUR')).toBeUndefined();
        expect(amountFromInput('-5', 'EUR')).toBe('-5');
    });
});

describe('times and days', () => {
    it('reads times as HH:MM only', () => {
        expect(['00:00', '09:30', '23:59'].every(isTime)).toBe(true);
        expect(['24:00', '12:60', '9:30', '09:30:00', 'noon', '', undefined, 930].some(isTime)).toBe(false);
        expect([minutesOf('00:00'), minutesOf('09:30'), minutesOf('23:59')]).toEqual([0, 570, 1439]);
    });

    it('reads days as real calendar dates, years under 100 included', () => {
        expect(isIsoDate('2028-02-29') && isIsoDate('0050-01-01') && isIsoDate('0001-01-01')).toBe(true);
        expect(isIsoDate('2026-02-30') || isIsoDate('2026-2-03') || isIsoDate('0000-01-01') || isIsoDate('12-11-2026')).toBe(false);
    });
});
