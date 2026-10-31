/**
 * Currencies a currency question can take, and the amount rules. An answer is
 * `{ code: 'EUR', amount: '12.50' }`: the ISO 4217 code and the amount as a
 * plain decimal string with at most as many decimals as the currency has.
 * The server's twin is common `currencies.py`; `docs/spec/currencies-v1.json`
 * is the table both tests compare with.
 */

/** Currency → number of decimals (the ISO 4217 minor unit exponent). */
export const CURRENCY_DECIMALS: Readonly<Record<string, number>> = {
    AED: 2,
    ARS: 2,
    AUD: 2,
    BGN: 2,
    BRL: 2,
    CAD: 2,
    CHF: 2,
    CLP: 0,
    CNY: 2,
    COP: 2,
    CZK: 2,
    DKK: 2,
    EGP: 2,
    EUR: 2,
    GBP: 2,
    HKD: 2,
    HUF: 2,
    IDR: 2,
    ILS: 2,
    INR: 2,
    ISK: 0,
    JPY: 0,
    KRW: 0,
    KWD: 3,
    MAD: 2,
    MXN: 2,
    MYR: 2,
    NGN: 2,
    NOK: 2,
    NZD: 2,
    PHP: 2,
    PLN: 2,
    RON: 2,
    SAR: 2,
    SEK: 2,
    SGD: 2,
    THB: 2,
    TND: 3,
    TRY: 2,
    UAH: 2,
    USD: 2,
    VND: 0,
    ZAR: 2
};

export const DEFAULT_CURRENCY = 'EUR';
/** At most this many allowed currencies on one question. */
export const CURRENCIES_MAX = 10;
/** An amount has at most this many digits before the decimal point. */
export const AMOUNT_MAX_INTEGER_DIGITS = 12;

export const CURRENCY_CODES: ReadonlyArray<string> = Object.keys(CURRENCY_DECIMALS);

export const isCurrencyCode = (code: unknown): code is string => typeof code === 'string' && Object.prototype.hasOwnProperty.call(CURRENCY_DECIMALS, code);

export const currencyDecimals = (code: string): number => (isCurrencyCode(code) ? CURRENCY_DECIMALS[code] : 2);

const AMOUNT = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/;
// A zero written with a minus ("-0", "-0.00") is not an amount: zero has one writing.
const NEGATIVE_ZERO = /^-0(?:\.0+)?$/;

/**
 * `amount` as a number when it is a plain decimal string with at most the
 * currency's decimals (any number when the code is unknown), else undefined:
 * no `+`, no thousands separators, no decimal comma, no exponent, no leading
 * zeros ("007"), no "-0", no more than AMOUNT_MAX_INTEGER_DIGITS integer digits.
 */
export function parseAmount(amount: unknown, code?: string): number | undefined {
    if (typeof amount !== 'string' || !AMOUNT.test(amount) || NEGATIVE_ZERO.test(amount)) return undefined;
    const [whole, fraction = ''] = amount.replace(/^-/, '').split('.');
    if (whole.length > AMOUNT_MAX_INTEGER_DIGITS) return undefined;
    if (isCurrencyCode(code) && fraction.length > CURRENCY_DECIMALS[code]) return undefined;
    return Number(amount);
}

/**
 * What a respondent typed as an amount, as the stored plain decimal string:
 * a comma or a dot is the decimal separator (Dutch and English habits), spaces
 * around the text are dropped, nothing else is guessed (thousands separators
 * are not accepted). Undefined when it is not an amount of that currency.
 */
export function amountFromInput(text: string, code?: string): string | undefined {
    const typed = text.trim().replace(',', '.');
    if (!typed) return undefined;
    // "-0" and "-0.00" are zero: stored without the minus, so zero reads one way
    const normalised = NEGATIVE_ZERO.test(typed) ? typed.slice(1) : typed;
    return parseAmount(normalised, code) === undefined ? undefined : normalised;
}

/**
 * The amount as a person reads it in `language` ("€ 12,50" in Dutch, "€12.50"
 * in English): the browser's number formatting with the currency's own
 * decimals. Text for responses and piped titles; the stored value is the
 * plain decimal string.
 */
export function formatAmount(currency: { code?: string; amount?: string } | undefined | null, language: string = 'en'): string {
    const amount = currency?.amount;
    const code = currency?.code;
    if (typeof amount !== 'string' || !amount) return '';
    const value = parseAmount(amount, code);
    if (value === undefined || !isCurrencyCode(code)) return [code, amount].filter(Boolean).join(' ');
    try {
        const digits = currencyDecimals(code);
        return new Intl.NumberFormat(language === 'nl' ? 'nl-NL' : language, { style: 'currency', currency: code, minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
    } catch {
        return `${code} ${amount}`;
    }
}

/** The export's stable text: the code, a space and the dot-decimal amount ("EUR 12.50"); '' when unanswered. */
export function currencyExportText(currency: { code?: string; amount?: string } | undefined | null): string {
    const amount = currency?.amount;
    if (typeof amount !== 'string' || !amount) return '';
    return [currency?.code, amount].filter(Boolean).join(' ');
}
