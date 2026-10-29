/**
 * Answer patterns that could freeze a browser (ReDoS).
 *
 * The server matches answer patterns with RE2 (linear time), but this
 * browser evaluates them with JavaScript's backtracking `RegExp`: a pattern
 * such as `^(a+)+$` takes exponential time on an answer like `aaaa…b`. This
 * finds the pattern shapes whose backtracking cost can explode, by a small
 * structural analysis of the parsed pattern (never a regex on a regex), so
 * the builder refuses them and the respondent form never hands them to
 * `RegExp`.
 *
 * The Python twin is `common/common/form_spec/pattern_safety.py` (same
 * algorithm, same hazard codes); the shared cases are
 * `docs/spec/pattern-safety.cases.json`, run by both. Keep the two in step.
 *
 * Hazards (conservative: a pattern that is merely unusual may be refused,
 * never one of these shapes accepted):
 * - backreference: `\1`, `\k<name>`, `(?P=name)`.
 * - nested_repeat: a repeated part (`x?` too) inside a repeated group that
 *   can start with what may follow it: `(a+)+`, `(a*)*`, `(\w+\s?)+`,
 *   `((ab)+)+`, `(a?a){30}`. `(\w+\s)+` is fine: the separator ends every
 *   iteration.
 * - overlapping_alternatives: a repeated group with two alternatives that
 *   can start with the same character: `(a|aa)+`.
 * - empty_repeat: a repeat (bounded or not) of something that can match
 *   nothing: `(\s*)+`, `(a?|b?){28}`.
 * - adjacent_repeats: repeats in one sequence that match the same
 *   characters multiply their work: `.*a.*a.*a`, `\d*\d*\d*`, `a?` twenty
 *   times in a row. Each variable repeat counts as its number of ways to
 *   match (an unbounded one as WORK_UNBOUNDED), the ones that overlap (also
 *   across a mandatory character they can match themselves, and from inside
 *   optional groups and alternations: `a*(?:b|a*)(?:c|a*)x`) multiply, and
 *   the product may not pass WORK_LIMIT: at most two unbounded repeats. A
 *   pattern that does not start with `^` is tried at every start of the
 *   answer, so it gets WORK_LIMIT / WORK_UNBOUNDED: `a{1,99}a{1,99}a{1,99}!`
 *   and `\d*\d*x` need a `^`, with it they are fine.
 * - inline_flags: `(?i)`, `(?i:...)` change what characters match; refused.
 * - too_complex: longer than PATTERN_MAX_LENGTH or nested too deep.
 * - unparseable: not a pattern this analysis can read (a broken one, or a
 *   syntax it does not know); a pattern that cannot be analysed is not
 *   trusted.
 *
 * Two overlapping unbounded repeats (`\d*\.?\d*`) cost quadratic time at
 * most and are allowed, as are lookarounds (their content is analysed on
 * its own). The check reduces the risk, it cannot prove that no pattern is
 * super-linear; the respondent form also tests only short answers
 * (PATTERN_TEST_MAX_LENGTH in answer-rules.ts), which bounds what is left.
 * Character sets are exact for classes, ranges and `\d \w \s`; Unicode
 * properties (`\p{L}`) are approximated by a superset, which can only add
 * overlaps, never hide one.
 */

export type PatternHazard = 'backreference' | 'nested_repeat' | 'overlapping_alternatives' | 'empty_repeat' | 'adjacent_repeats' | 'too_complex' | 'unparseable' | 'inline_flags';

export const PATTERN_HAZARDS: ReadonlyArray<PatternHazard> = ['backreference', 'nested_repeat', 'overlapping_alternatives', 'empty_repeat', 'adjacent_repeats', 'too_complex', 'unparseable', 'inline_flags'];

/** The same cap as the form spec and the server (common form_spec PATTERN_MAX_LENGTH). */
export const PATTERN_MAX_LENGTH = 200;
const MAX_DEPTH = 40;
/**
 * Work estimate per start position: an unbounded repeat counts as this many
 * ways to match (about the longest text the browser tests), and the repeats
 * of one sequence that overlap may multiply to at most WORK_LIMIT.
 */
const WORK_UNBOUNDED = 1000;
const WORK_LIMIT = 1_000_000;

/** What the server says (common pattern_safety.py HAZARD_MESSAGES); the builder shows the translated text (`builder` PATTERN_HAZARD.*). */
export const PATTERN_HAZARD_MESSAGES: Record<PatternHazard, string> = {
    backreference: 'A pattern cannot refer back to an earlier group (\\1): it can take a browser very long to check.',
    nested_repeat: 'A repeated group inside a repeated group, such as (a+)+, can take a browser very long to check. Make each repeat end in a separator or use one repeat.',
    overlapping_alternatives: 'A repeated group whose choices can start with the same character, such as (a|aa)+, can take a browser very long to check. Make the choices start differently or merge them.',
    empty_repeat: 'A repeated group that can match nothing, such as (a?)*, can take a browser very long to check.',
    adjacent_repeats: 'Several repeats in a row that match the same characters, such as \\d*\\d*\\d*, can take a browser very long to check. Use fewer, or start the pattern with ^.',
    too_complex: 'This pattern is too long or too complex to check safely. Shorten or simplify it.',
    unparseable: 'This pattern could not be read to check it safely. Simplify it.',
    inline_flags: 'Flags written inside a pattern, such as (?i), are not supported. Match both cases with a class such as [Aa] instead.'
};

const MAX_CODEPOINT = 0x10ffff;
type Ranges = ReadonlyArray<readonly [number, number]>;
const ALL: Ranges = [[0, MAX_CODEPOINT]];
const NONE: Ranges = [];
const LINE_TERMINATORS: Ranges = [
    [10, 10],
    [13, 13],
    [0x2028, 0x2029]
];
const DIGITS: Ranges = [[48, 57]];
const WORD: Ranges = [
    [48, 57],
    [65, 90],
    [95, 95],
    [97, 122]
];
const SPACE: Ranges = [
    [9, 13],
    [32, 32],
    [0xa0, 0xa0],
    [0x1680, 0x1680],
    [0x2000, 0x200a],
    [0x2028, 0x2029],
    [0x202f, 0x202f],
    [0x205f, 0x205f],
    [0x3000, 0x3000],
    [0xfeff, 0xfeff]
];
const LETTERS_SUPERSET: Ranges = [
    [65, 90],
    [97, 122],
    [0x80, MAX_CODEPOINT]
];
const NUMBERS_SUPERSET: Ranges = [
    [48, 57],
    [0x80, MAX_CODEPOINT]
];

class Unparseable extends Error {}
class TooDeep extends Error {}
class InlineFlags extends Error {}

function norm(ranges: Array<readonly [number, number]>): Ranges {
    const sorted = [...ranges].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    const merged: Array<[number, number]> = [];
    for (const [low, high] of sorted) {
        const last = merged[merged.length - 1];
        if (last && low <= last[1] + 1) {
            if (high > last[1]) last[1] = high;
        } else {
            merged.push([low, high]);
        }
    }
    return merged;
}

function negate(ranges: Ranges): Ranges {
    const out: Array<[number, number]> = [];
    let start = 0;
    for (const [low, high] of ranges) {
        if (low > start) out.push([start, low - 1]);
        start = high + 1;
    }
    if (start <= MAX_CODEPOINT) out.push([start, MAX_CODEPOINT]);
    return out;
}

function union(a: Ranges, b: Ranges): Ranges {
    if (!a.length) return b;
    if (!b.length) return a;
    return norm([...a, ...b]);
}

function overlap(a: Ranges, b: Ranges): boolean {
    let i = 0;
    let j = 0;
    while (i < a.length && j < b.length) {
        if (a[i][1] < b[j][0]) i++;
        else if (b[j][1] < a[i][0]) j++;
        else return true;
    }
    return false;
}

function propertyRanges(name: string, negated: boolean): Ranges {
    const key = (name.split('=').pop() ?? '').trim();
    if (negated) return ALL;
    if (key.startsWith('L')) return LETTERS_SUPERSET;
    if (key.startsWith('N')) return NUMBERS_SUPERSET;
    return ALL;
}

// A node: char (a set), zero (matches nothing, e.g. `$`), bol (`^`), seq, alt,
// rep (body, min, max or null for unbounded), look (a lookaround's content),
// backref.
type Node =
    { kind: 'char'; set: Ranges } | { kind: 'zero' } | { kind: 'bol' } | { kind: 'seq'; items: Node[] } | { kind: 'alt'; branches: Node[] } | { kind: 'rep'; body: Node; min: number; max: number | null } | { kind: 'look'; body: Node } | { kind: 'backref' };

const ZERO: Node = { kind: 'zero' };
const BOL: Node = { kind: 'bol' };
const isDigit = (char: string | undefined): boolean => char !== undefined && char >= '0' && char <= '9';
// (no RegExp in here: the respondent form's tests watch that no pattern is tested)
const isAlpha = (char: string | undefined): boolean => char !== undefined && ((char >= 'a' && char <= 'z') || (char >= 'A' && char <= 'Z'));
const isHex = (char: string): boolean => (char >= '0' && char <= '9') || (char >= 'a' && char <= 'f') || (char >= 'A' && char <= 'F');

class Parser {
    private chars: string[];
    private i = 0;
    private depth = 0;
    backref = false;

    constructor(pattern: string) {
        this.chars = Array.from(pattern);
    }

    private eof(): boolean {
        return this.i >= this.chars.length;
    }

    private peek(offset = 0): string {
        return this.chars[this.i + offset] ?? '';
    }

    private slice(from: number, to: number): string {
        return this.chars.slice(from, to).join('');
    }

    private find(char: string, from: number): number {
        return this.chars.indexOf(char, from);
    }

    parse(): Node {
        const node = this.alternation();
        if (!this.eof()) throw new Unparseable(); // a stray ")"
        return node;
    }

    private alternation(): Node {
        this.depth++;
        if (this.depth > MAX_DEPTH) throw new TooDeep();
        const branches = [this.sequence()];
        while (this.peek() === '|') {
            this.i++;
            branches.push(this.sequence());
        }
        this.depth--;
        return branches.length === 1 ? branches[0] : { kind: 'alt', branches };
    }

    private sequence(): Node {
        const items: Node[] = [];
        while (!this.eof() && this.peek() !== '|' && this.peek() !== ')') {
            const atom = this.quantified(this.atom());
            // a group without a repeat is just its content
            if (atom.kind === 'seq') items.push(...atom.items);
            else items.push(atom);
        }
        return items.length === 1 ? items[0] : { kind: 'seq', items };
    }

    private quantified(atom: Node): Node {
        const char = this.peek();
        let min: number;
        let max: number | null;
        if (char === '*') {
            min = 0;
            max = null;
            this.i++;
        } else if (char === '+') {
            min = 1;
            max = null;
            this.i++;
        } else if (char === '?') {
            min = 0;
            max = 1;
            this.i++;
        } else if (char === '{') {
            const found = this.braces();
            if (!found) return atom;
            [min, max] = found;
        } else {
            return atom;
        }
        // lazy or possessive suffix
        if (this.peek() === '?' || this.peek() === '+') this.i++;
        if (atom.kind === 'zero' || atom.kind === 'bol' || atom.kind === 'look') return atom; // nothing to repeat
        return { kind: 'rep', body: atom, min, max };
    }

    /** {n} {n,} {n,m} at the cursor, consumed; null (nothing consumed) when it is not a quantifier, which then reads as literal text. */
    private braces(): [number, number | null] | null {
        let j = this.i + 1;
        const start = j;
        while (isDigit(this.chars[j])) j++;
        if (j === start) return null;
        const min = parseInt(this.slice(start, j), 10);
        let max: number | null = min;
        if (this.chars[j] === ',') {
            j++;
            const from = j;
            while (isDigit(this.chars[j])) j++;
            max = j > from ? parseInt(this.slice(from, j), 10) : null;
        }
        if (this.chars[j] !== '}') return null;
        this.i = j + 1;
        return [min, max];
    }

    private atom(): Node {
        const char = this.peek();
        if (char === '(') return this.group();
        if (char === '[') return { kind: 'char', set: this.charClass() };
        if (char === '.') {
            this.i++;
            return { kind: 'char', set: negate(LINE_TERMINATORS) };
        }
        if (char === '^') {
            this.i++;
            return BOL;
        }
        if (char === '$') {
            this.i++;
            return ZERO;
        }
        if (char === '\\') return this.escape();
        if (char === '*' || char === '+' || char === '?') throw new Unparseable(); // nothing to repeat
        this.i++;
        const code = char.codePointAt(0) as number;
        return { kind: 'char', set: [[code, code]] };
    }

    private group(): Node {
        this.i++; // (
        let look = false;
        if (this.peek() === '?') {
            const rest = this.slice(this.i + 1, this.i + 4);
            if (rest.startsWith('=') || rest.startsWith('!')) {
                look = true;
                this.i += 2;
            } else if (rest.startsWith('<=') || rest.startsWith('<!')) {
                look = true;
                this.i += 3;
            } else if (rest.startsWith('#')) {
                const end = this.find(')', this.i);
                if (end < 0) throw new Unparseable();
                this.i = end + 1;
                return ZERO;
            } else if (rest.startsWith('P=')) {
                const end = this.find(')', this.i);
                if (end < 0) throw new Unparseable();
                this.i = end + 1;
                this.backref = true;
                return { kind: 'backref' };
            } else if (rest.startsWith('P<') || rest.startsWith('<')) {
                const end = this.find('>', this.i);
                if (end < 0) throw new Unparseable();
                this.i = end + 1;
            } else if (rest.startsWith(':') || rest.startsWith('>')) {
                this.i += 2;
            } else {
                // inline flags: (?i) is a flag-only group, (?i:...) scopes them
                let j = this.i + 1;
                while (j < this.chars.length && (isAlpha(this.chars[j]) || this.chars[j] === '-')) j++;
                if (j >= this.chars.length || j === this.i + 1) throw new Unparseable();
                if (this.chars[j] !== ')' && this.chars[j] !== ':') throw new Unparseable();
                // (?i) and (?i:...) change what characters match; the analysis
                // works on exact sets, so they are refused
                throw new InlineFlags();
            }
        }
        const body = this.alternation();
        if (this.peek() !== ')') throw new Unparseable();
        this.i++;
        return look ? { kind: 'look', body } : body;
    }

    private escape(): Node {
        this.i++; // backslash
        if (this.eof()) throw new Unparseable();
        const char = this.peek();
        this.i++;
        if (char === 'A') return BOL;
        if ('bBZzG'.includes(char)) return ZERO;
        if ('123456789'.includes(char)) {
            this.backref = true;
            return { kind: 'backref' };
        }
        if (char === 'k' && this.peek() === '<') {
            this.backref = true;
            const end = this.find('>', this.i);
            this.i = end >= 0 ? end + 1 : this.chars.length;
            return { kind: 'backref' };
        }
        return { kind: 'char', set: this.classEscape(char) };
    }

    /** The set an escape stands for (after the backslash and its letter, both consumed); a lone escaped character stands for itself. */
    private classEscape(char: string): Ranges {
        switch (char) {
            case 'd':
                return DIGITS;
            case 'D':
                return negate(DIGITS);
            case 'w':
                return WORD;
            case 'W':
                return negate(WORD);
            case 's':
                return SPACE;
            case 'S':
                return negate(SPACE);
            case 'p':
            case 'P': {
                let name: string;
                if (this.peek() === '{') {
                    const end = this.find('}', this.i);
                    if (end < 0) throw new Unparseable();
                    name = this.slice(this.i + 1, end);
                    this.i = end + 1;
                } else {
                    name = this.peek();
                    this.i++;
                }
                return propertyRanges(name, char === 'P');
            }
            case 'x':
                return this.hex(2);
            case 'u': {
                if (this.peek() === '{') {
                    const end = this.find('}', this.i);
                    if (end < 0) throw new Unparseable();
                    const digits = this.slice(this.i + 1, end);
                    this.i = end + 1;
                    return this.code(digits);
                }
                return this.hex(4);
            }
            case 'c':
                this.i++;
                return ALL; // control character: not worth modelling
            case 'n':
                return [[10, 10]];
            case 'r':
                return [[13, 13]];
            case 't':
                return [[9, 9]];
            case 'f':
                return [[12, 12]];
            case 'v':
                return [[11, 11]];
            case '0':
                return [[0, 0]];
            default: {
                const code = char.codePointAt(0) as number;
                return [[code, code]];
            }
        }
    }

    private hex(count: number): Ranges {
        const digits = this.slice(this.i, this.i + count);
        this.i += Array.from(digits).length;
        return this.code(digits);
    }

    private code(digits: string): Ranges {
        if (!digits || !Array.from(digits).every(isHex)) return ALL;
        const code = parseInt(digits, 16);
        return code > MAX_CODEPOINT ? ALL : [[code, code]];
    }

    private charClass(): Ranges {
        this.i++; // [
        let negated = false;
        if (this.peek() === '^') {
            negated = true;
            this.i++;
        }
        const ranges: Array<readonly [number, number]> = [];
        let first = true;
        for (;;) {
            if (this.eof()) throw new Unparseable();
            if (this.peek() === ']' && !first) {
                this.i++;
                break;
            }
            first = false;
            const low = this.classAtom(ranges);
            if (low === null) continue;
            // a range a-z
            if (this.peek() === '-' && this.peek(1) !== ']' && this.peek(1) !== '') {
                this.i++;
                const high = this.classAtom(ranges);
                if (high === null) {
                    ranges.push([low, low], [45, 45]);
                    continue;
                }
                if (high < low) throw new Unparseable();
                ranges.push([low, high]);
            } else {
                ranges.push([low, low]);
            }
        }
        const result = norm(ranges);
        return negated ? negate(result) : result;
    }

    /** One class member: the code of a single character, or null after adding a whole set (`\d`, `\p{L}`) to `ranges`. */
    private classAtom(ranges: Array<readonly [number, number]>): number | null {
        const char = this.peek();
        this.i++;
        if (char !== '\\') return char.codePointAt(0) as number;
        if (this.eof()) throw new Unparseable();
        const escaped = this.peek();
        this.i++;
        if (escaped === 'b') return 8;
        if ('dDwWsSpP'.includes(escaped)) {
            ranges.push(...this.classEscape(escaped));
            return null;
        }
        const found = this.classEscape(escaped);
        if (found.length === 1 && found[0][0] === found[0][1]) return found[0][0];
        ranges.push(...found);
        return null;
    }
}

class Analysis {
    problem: PatternHazard | null = null;
    // by node identity: nodes are shared constants only for ZERO, whose info is fixed
    private infos = new Map<Node, [boolean, Ranges]>();
    private alphabets = new Map<Node, Ranges>();
    private altWeights = new Map<Node, number>();
    anchored = false;
    private ids = 0;

    flag(code: PatternHazard): void {
        if (this.problem === null) this.problem = code;
    }

    /** [can match the empty string, characters it can start with]. */
    info(node: Node): [boolean, Ranges] {
        const cached = this.infos.get(node);
        if (cached) return cached;
        let result: [boolean, Ranges];
        switch (node.kind) {
            case 'char':
                result = [false, node.set];
                break;
            case 'zero':
            case 'bol':
            case 'look':
                result = [true, NONE];
                break;
            case 'backref':
                result = [true, ALL];
                break;
            case 'seq': {
                let nullable = true;
                let first: Ranges = NONE;
                for (const item of node.items) {
                    const [itemNullable, itemFirst] = this.info(item);
                    first = union(first, itemFirst);
                    if (!itemNullable) {
                        nullable = false;
                        break;
                    }
                }
                result = [nullable, first];
                break;
            }
            case 'alt': {
                let nullable = false;
                let first: Ranges = NONE;
                for (const branch of node.branches) {
                    const [branchNullable, branchFirst] = this.info(branch);
                    nullable = nullable || branchNullable;
                    first = union(first, branchFirst);
                }
                result = [nullable, first];
                break;
            }
            case 'rep': {
                const [bodyNullable, bodyFirst] = this.info(node.body);
                result = [bodyNullable || node.min === 0, bodyFirst];
                break;
            }
        }
        this.infos.set(node, result);
        return result;
    }

    walk(node: Node, follow: Ranges, inLoop: boolean): void {
        if (this.problem !== null) return;
        switch (node.kind) {
            case 'backref':
                this.flag('backreference');
                break;
            case 'look':
                this.walk(node.body, NONE, inLoop);
                break;
            case 'seq': {
                let ahead = follow;
                for (let index = node.items.length - 1; index >= 0; index--) {
                    const item = node.items[index];
                    this.walk(item, ahead, inLoop);
                    const [itemNullable, itemFirst] = this.info(item);
                    ahead = itemNullable ? union(itemFirst, ahead) : itemFirst;
                }
                this.adjacent(node.items);
                break;
            }
            case 'alt': {
                for (const branch of node.branches) this.walk(branch, follow, inLoop);
                if (inLoop) {
                    let seen: Ranges = NONE;
                    for (const branch of node.branches) {
                        const first = this.info(branch)[1];
                        if (overlap(seen, first)) {
                            this.flag('overlapping_alternatives');
                            return;
                        }
                        seen = union(seen, first);
                    }
                }
                break;
            }
            case 'rep': {
                const { body, min, max } = node;
                const [nullable, first] = this.info(body);
                // a fixed count (x{4}) has one way to match; a variable one
                // (x?, x+, x{2,5}) that can start what a loop's next round or
                // exit starts with is ambiguous
                const variable = max === null || max !== min;
                if (inLoop && variable && overlap(first, follow)) {
                    this.flag('nested_repeat');
                    return;
                }
                if (max !== null && max <= 1) {
                    this.walk(body, follow, inLoop); // x? : not a loop itself
                    return;
                }
                this.walk(body, union(first, follow), true);
                // any repeat of something that can match nothing, bounded or
                // not: (a?|b?){28} has as many ways to match as it has rounds
                if (nullable && this.problem === null) this.flag('empty_repeat');
                break;
            }
        }
    }

    /** Every character the node can match, anywhere in it. */
    private alphabet(node: Node): Ranges {
        const cached = this.alphabets.get(node);
        if (cached) return cached;
        let result: Ranges;
        switch (node.kind) {
            case 'char':
                result = node.set;
                break;
            case 'zero':
            case 'bol':
            case 'look':
                result = NONE;
                break;
            case 'backref':
                result = ALL;
                break;
            case 'rep':
                result = this.alphabet(node.body);
                break;
            case 'seq':
                result = node.items.reduce<Ranges>((all, child) => union(all, this.alphabet(child)), NONE);
                break;
            case 'alt':
                result = node.branches.reduce<Ranges>((all, child) => union(all, this.alphabet(child)), NONE);
                break;
        }
        this.alphabets.set(node, result);
        return result;
    }

    /**
     * The ways of matching the same text that a sequence holds, in order:
     * `atom` for a variable repeat or an ambiguous alternation, wherever it
     * sits (inside an optional group or a loop too), `mand` for a character
     * that must be there, and `cut` where mandatory characters end repeats of
     * an optional group. A variable repeat has (max - min + 1) ways, an
     * unbounded one WORK_UNBOUNDED. `gates`: see `optional`.
     */
    private flatten(items: Node[], out: Entry[]): void {
        for (const item of items) {
            if (item.kind === 'seq') {
                this.flatten(item.items, out);
            } else if (item.kind === 'rep') {
                const { body, min, max } = item;
                let inner: Entry[] = [];
                this.flatten(body.kind === 'seq' ? body.items : [body], inner);
                if (max !== null && max <= 1) {
                    // x? or x{1}: what is inside counts, wherever it is
                    if (min === 0) {
                        inner = this.optional(inner);
                        if (!inner.some((entry) => entry.kind === 'atom')) inner.push(this.atom(this.alphabet(body), 2));
                    }
                    out.push(...inner);
                    continue;
                }
                const ways = max === null ? WORK_UNBOUNDED : Math.min(max - min + 1, WORK_UNBOUNDED);
                if (inner.some((entry) => entry.kind === 'atom')) {
                    // a loop over variable repeats: they count, a few rounds of
                    // them (the loop's own ambiguity is nested_repeat's), and
                    // so do the rounds themselves
                    inner = this.optional(inner, true);
                    for (let round = 0; round < Math.min(Math.max(min, 1), 3); round++) out.push(...inner);
                }
                this.emit(item, ways, out);
            } else if (item.kind === 'alt') {
                this.emit(item, this.altWeight(item), out);
            } else if (item.kind === 'char') {
                out.push({ kind: 'mand', set: item.set });
            }
        }
    }

    private atom(set: Ranges, ways: number): Atom {
        this.ids++;
        return { kind: 'atom', set, ways, gates: NONE, id: this.ids };
    }

    /**
     * The entries of an optional group as they go into the sequence around
     * it. The group may be skipped, so its mandatory characters never end the
     * repeats outside it; they end the repeats inside it (a `cut`: those
     * multiply with what came before the cut, not after), and keep the
     * repeats after them from multiplying with outside repeats that cannot
     * match them (`gates`). `wrap`: the group is a loop, so its leading
     * mandatory characters also follow its last repeats.
     */
    private optional(inner: Entry[], wrap = false): Entry[] {
        const result: Entry[] = [];
        const live = new Map<number, Ranges>(); // repeats not ended yet: id -> characters
        let gates: Ranges = NONE;
        const leading: Mand[] = []; // mandatory characters before the first repeat
        const mandatory = (set: Ranges) => {
            if (live.size && ![...live.values()].some((other) => overlap(other, set))) {
                result.push({ kind: 'cut', ids: new Set(live.keys()) });
                live.clear();
            }
        };
        for (const entry of inner) {
            if (entry.kind === 'atom') {
                result.push({ ...entry, gates: union(entry.gates, gates) });
                live.set(entry.id, entry.set);
            } else if (entry.kind === 'cut') {
                result.push(entry);
                entry.ids.forEach((id) => live.delete(id));
            } else {
                if (!live.size && !result.some((e) => e.kind === 'atom')) leading.push(entry);
                gates = union(gates, entry.set);
                mandatory(entry.set);
            }
        }
        if (wrap) for (const entry of leading) mandatory(entry.set);
        return result;
    }

    private emit(item: Node, ways: number, out: Entry[]): void {
        if (ways > 1) out.push(this.atom(this.alphabet(item), ways));
        else if (!this.info(item)[0]) out.push({ kind: 'mand', set: this.alphabet(item) });
    }

    /** An alternation's ways: one per choice when the choices can start alike, times the most its choices hold inside themselves. */
    private altWeight(item: Node & { kind: 'alt' }): number {
        const cached = this.altWeights.get(item);
        if (cached !== undefined) return cached;
        let seen: Ranges = NONE;
        let alike = false;
        let inside = 1;
        for (const branch of item.branches) {
            const first = this.info(branch)[1];
            if (overlap(seen, first)) alike = true;
            seen = union(seen, first);
            inside = Math.max(inside, this.chainCost(branch.kind === 'seq' ? branch.items : [branch]));
        }
        const result = (alike ? item.branches.length : 1) * inside;
        this.altWeights.set(item, result);
        return result;
    }

    /**
     * The most work a sequence's variable repeats add up to: those that match
     * the same characters multiply (`.*a.*a.*a` is cubic, `a?a?a?…a?aaa`
     * exponential), also across a mandatory character they can match
     * themselves (the `a`) and from inside optional groups and alternations
     * (`a*(?:b|a*)(?:c|a*)x`).
     */
    private chainCost(items: Node[]): number {
        const flat: Entry[] = [];
        this.flatten(items, flat);
        let chain: Atom[] = [];
        let best = 1;
        for (const entry of flat) {
            if (entry.kind === 'atom') {
                let cost = entry.ways;
                // (a character that had to be there between them, which the earlier repeat cannot match, keeps them apart)
                for (const other of chain) if (overlap(other.set, entry.set) && (!entry.gates.length || overlap(other.set, entry.gates))) cost *= other.ways;
                best = Math.max(best, cost);
                chain.push(entry);
            } else if (entry.kind === 'cut') {
                chain = chain.filter((other) => !entry.ids.has(other.id));
            } else if (!chain.some((other) => overlap(other.set, entry.set))) {
                chain = []; // a mandatory character the repeats cannot match
            }
        }
        return best;
    }

    /**
     * The work of a sequence may not pass WORK_LIMIT: two overlapping
     * unbounded repeats are the most. A pattern that does not start with `^`
     * is tried at every start position of the answer, so its limit is divided
     * by WORK_UNBOUNDED (about the longest answer tested).
     */
    private adjacent(items: Node[]): void {
        const limit = this.anchored ? WORK_LIMIT : WORK_LIMIT / WORK_UNBOUNDED;
        if (this.chainCost(items) > limit) this.flag('adjacent_repeats');
    }
}

type Atom = { kind: 'atom'; set: Ranges; ways: number; gates: Ranges; id: number };
type Mand = { kind: 'mand'; set: Ranges };
type Entry = Atom | Mand | { kind: 'cut'; ids: Set<number> };

/** Whether every way into the pattern starts with `^` (or `\A`). */
function isAnchored(node: Node): boolean {
    if (node.kind === 'bol') return true;
    if (node.kind === 'alt') return node.branches.every(isAnchored);
    if (node.kind === 'seq') {
        for (const item of node.items) {
            if (item.kind === 'zero') continue; // a comment, \b
            return isAnchored(item);
        }
    }
    return false;
}

const memo = new Map<string, PatternHazard | null>();
const MEMO_LIMIT = 512;

/** null when `pattern` is safe to evaluate with a backtracking engine, else the hazard. */
export function patternHazard(pattern: string | undefined | null): PatternHazard | null {
    if (!pattern) return null;
    const known = memo.get(pattern);
    if (known !== undefined) return known;
    const result = analyse(pattern);
    if (memo.size >= MEMO_LIMIT) memo.clear();
    memo.set(pattern, result);
    return result;
}

function analyse(pattern: string): PatternHazard | null {
    if (Array.from(pattern).length > PATTERN_MAX_LENGTH) return 'too_complex';
    const parser = new Parser(pattern);
    let tree: Node;
    try {
        tree = parser.parse();
    } catch (error) {
        if (error instanceof InlineFlags) return 'inline_flags';
        return error instanceof TooDeep ? 'too_complex' : 'unparseable';
    }
    if (parser.backref) return 'backreference';
    const analysis = new Analysis();
    analysis.anchored = isAnchored(tree);
    try {
        analysis.walk(tree, NONE, false);
    } catch {
        return 'too_complex';
    }
    return analysis.problem;
}
