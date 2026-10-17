/**
 * Decimal numbers for expressions (spec: docs/spec/expressions-v1.md, "Numbers").
 *
 * A number is `coef × 10^exp` with an integer coefficient, kept to at most
 * 15 significant digits and at most 15 decimal places, and |x| < 1e15. Every
 * operation result is rounded back into that range half away from zero; a
 * result outside the range is `null`. Because a value never has more than 15
 * significant digits, it converts to a JS number and back without loss.
 *
 * The Python twin (common/common/expressions/decimal_num.py) implements the
 * same algorithm on integers, so both sides agree digit for digit.
 */

const ZERO_BIG = BigInt(0);
const ONE_BIG = BigInt(1);
const TEN_BIG = BigInt(10);

/** Significant digits kept. */
export const MAX_DIGITS = 15;
/** Decimal places kept. */
export const MAX_SCALE = 15;
/** Largest allowed adjusted exponent (|x| < 10^15). */
const MAX_ADJ = 14;
/** Digits below this exponent never change a half-away rounding at -MAX_SCALE or above. */
const GUARD_EXP = -(MAX_SCALE + 2);

export type RoundingMode = 'half_away' | 'floor' | 'ceil';

function pow10(n: number): bigint {
    let result = ONE_BIG;
    let base = TEN_BIG;
    let k = n;
    while (k > 0) {
        if (k & 1) result *= base;
        base *= base;
        k >>= 1;
    }
    return result;
}

function absBig(v: bigint): bigint {
    return v < ZERO_BIG ? -v : v;
}

function digitCount(v: bigint): number {
    return absBig(v).toString().length;
}

export class Dec {
    readonly coef: bigint;
    readonly exp: number;

    private constructor(coef: bigint, exp: number) {
        this.coef = coef;
        this.exp = exp;
    }

    static readonly ZERO = new Dec(ZERO_BIG, 0);

    /** Round `coef × 10^exp` into range; null when it overflows. */
    static make(coef: bigint, exp: number): Dec | null {
        if (coef === ZERO_BIG) return Dec.ZERO;
        const adj = digitCount(coef) - 1 + exp;
        let c = coef;
        let e = exp;
        const position = Math.max(adj - (MAX_DIGITS - 1), -MAX_SCALE);
        if (e < position) {
            c = roundCoef(c, position - e, 'half_away');
            e = position;
        }
        if (c === ZERO_BIG) return Dec.ZERO;
        if (digitCount(c) - 1 + e > MAX_ADJ) return null;
        while (c % TEN_BIG === ZERO_BIG) {
            c /= TEN_BIG;
            e += 1;
        }
        return new Dec(c, e);
    }

    static fromInt(n: number): Dec {
        return Dec.make(BigInt(n), 0) as Dec;
    }

    /**
     * Parse `[+-]digits[.digits][e[+-]digits]` (ASCII only, no surrounding
     * whitespace). Returns undefined when the text is not a number and null
     * when it is a number outside the range.
     */
    static parse(text: string): Dec | null | undefined {
        const match = /^([+-]?)([0-9]*)(?:\.([0-9]*))?(?:[eE]([+-]?[0-9]+))?$/.exec(text);
        if (!match) return undefined;
        const intPart = match[2];
        const fracPart = match[3] ?? '';
        if (intPart === '' && fracPart === '') return undefined;
        const negative = match[1] === '-';
        const expText = match[4] ?? '0';
        // Exponents this long are far outside the range either way.
        const expDigits = expText.replace(/^[+-]/, '').replace(/^0+/, '');
        let exp10: number;
        if (expDigits.length > 6) exp10 = expText.startsWith('-') ? -Infinity : Infinity;
        else exp10 = Number(expText);
        let digits = (intPart + fracPart).replace(/^0+/, '');
        if (digits === '') return Dec.ZERO;
        // value = digits × 10^(exp10 - fracPart.length)
        let exp = exp10 - fracPart.length;
        const adj = digits.length - 1 + exp;
        if (adj > MAX_ADJ) return null;
        if (adj < GUARD_EXP) return Dec.ZERO;
        // Digits below GUARD_EXP cannot change the rounded result.
        if (exp < GUARD_EXP) {
            const drop = GUARD_EXP - exp;
            digits = digits.slice(0, Math.max(digits.length - drop, 0));
            exp = GUARD_EXP;
            if (digits === '') return Dec.ZERO;
        }
        const coef = BigInt(digits);
        return Dec.make(negative ? -coef : coef, exp);
    }

    /** A JS number as a decimal: its shortest round-trip text, rounded into range. */
    static fromNumber(n: number): Dec | null {
        if (!Number.isFinite(n)) return null;
        return Dec.parse(String(n)) ?? null;
    }

    isZero(): boolean {
        return this.coef === ZERO_BIG;
    }

    sign(): number {
        return this.coef > ZERO_BIG ? 1 : this.coef < ZERO_BIG ? -1 : 0;
    }

    isInteger(): boolean {
        return this.exp >= 0;
    }

    neg(): Dec {
        return this.isZero() ? this : new Dec(-this.coef, this.exp);
    }

    abs(): Dec {
        return this.coef < ZERO_BIG ? new Dec(-this.coef, this.exp) : this;
    }

    add(other: Dec): Dec | null {
        const e = Math.min(this.exp, other.exp);
        return Dec.make(this.coef * pow10(this.exp - e) + other.coef * pow10(other.exp - e), e);
    }

    sub(other: Dec): Dec | null {
        return this.add(other.neg());
    }

    mul(other: Dec): Dec | null {
        return Dec.make(this.coef * other.coef, this.exp + other.exp);
    }

    /** Quotient rounded half away from zero; null when dividing by zero. */
    div(other: Dec): Dec | null {
        if (other.isZero()) return null;
        // Truncate the exact quotient at 10^GUARD_EXP; one guard digit below
        // the rounding position is enough for half-away rounding.
        const shift = this.exp - other.exp - GUARD_EXP;
        const numerator = shift >= 0 ? this.coef * pow10(shift) : this.coef;
        const denominator = shift >= 0 ? other.coef : other.coef * pow10(-shift);
        return Dec.make(numerator / denominator, GUARD_EXP);
    }

    /** Remainder with the sign of the dividend; null when dividing by zero. */
    mod(other: Dec): Dec | null {
        if (other.isZero()) return null;
        const e = Math.min(this.exp, other.exp);
        const a = this.coef * pow10(this.exp - e);
        const b = other.coef * pow10(other.exp - e);
        return Dec.make(a % b, e);
    }

    /** Round to `places` decimal places (negative: tens, hundreds, …). */
    round(places: number, mode: RoundingMode = 'half_away'): Dec | null {
        const position = -places;
        if (this.exp >= position) return this;
        return Dec.make(roundCoef(this.coef, position - this.exp, mode), position);
    }

    cmp(other: Dec): number {
        const e = Math.min(this.exp, other.exp);
        const a = this.coef * pow10(this.exp - e);
        const b = other.coef * pow10(other.exp - e);
        return a < b ? -1 : a > b ? 1 : 0;
    }

    /** Integer value when this is a whole number (always safe: |x| < 1e15). */
    toInteger(): number | undefined {
        if (!this.isInteger()) return undefined;
        return Number(this.coef * pow10(this.exp));
    }

    /** Plain decimal text: no exponent, no trailing zeros, "0" for zero. */
    toString(): string {
        if (this.isZero()) return '0';
        const negative = this.coef < ZERO_BIG;
        const digits = absBig(this.coef).toString();
        let text: string;
        if (this.exp >= 0) {
            text = digits + '0'.repeat(this.exp);
        } else {
            const places = -this.exp;
            const padded = digits.length <= places ? '0'.repeat(places - digits.length + 1) + digits : digits;
            text = `${padded.slice(0, padded.length - places)}.${padded.slice(padded.length - places)}`;
        }
        return negative ? `-${text}` : text;
    }

    toNumber(): number {
        return Number(this.toString());
    }
}

/** Drop `drop` (> 0) trailing digits of `coef`, rounding by `mode`. */
function roundCoef(coef: bigint, drop: number, mode: RoundingMode): bigint {
    const divisor = pow10(drop);
    const quotient = coef / divisor; // truncates toward zero
    const remainder = coef % divisor;
    if (remainder === ZERO_BIG) return quotient;
    const negative = coef < ZERO_BIG;
    switch (mode) {
        case 'floor':
            return negative ? quotient - ONE_BIG : quotient;
        case 'ceil':
            return negative ? quotient : quotient + ONE_BIG;
        default:
            if (absBig(remainder) * BigInt(2) >= divisor) return negative ? quotient - ONE_BIG : quotient + ONE_BIG;
            return quotient;
    }
}
