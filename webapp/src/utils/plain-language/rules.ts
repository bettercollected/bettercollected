import jargonEn from './jargon-en.json';
import jargonNl from './jargon-nl.json';
import type { PlainLanguage } from './language';
import { splitClauses, splitSentences, tokenize } from './text';

export type PlainLanguageRule = 'long-sentence' | 'passive' | 'jargon' | 'double-question';

export interface PlainLanguageHint {
    /** Stable per text and finding — used to dismiss one hint for one field. */
    id: string;
    rule: PlainLanguageRule;
    /** Language whose rule matched; 'any' for language-neutral findings. */
    language: PlainLanguage | 'any';
    /** The words in the text that triggered the hint, as written. */
    match?: string;
    /** A plainer alternative (jargon). */
    suggestion?: string;
    /** Sentence length: the sentence's word count and the limit it went over. */
    words?: number;
    limit?: number;
    /** Double questions: which pattern matched. */
    variant?: 'and-or' | 'two-question-marks' | 'joined-questions';
}

// ---------------------------------------------------------------------------
// Sentence length
// ---------------------------------------------------------------------------

/**
 * Most words a sentence may have before we suggest splitting it.
 *
 * - Dutch (B1): the plain-language guidance behind the government's Direct
 *   Duidelijk programme and the Rijksoverheid writing guides advises short
 *   sentences of at most 15 to 20 words. We take the upper end, 20, so only
 *   sentences that are clearly too long are flagged.
 * - English: the GOV.UK style guide asks for sentences of 25 words or fewer
 *   (the Plain English Campaign recommends an *average* of 15 to 20).
 *
 * A piped answer counts as one word. When a text's language is unknown we use
 * the higher limit: missing a hint is better than a false one.
 */
export const SENTENCE_WORD_LIMIT: Record<PlainLanguage, number> = { nl: 20, en: 25 };

export function checkSentenceLength(text: string, languages: PlainLanguage[]): PlainLanguageHint[] {
    const limit = Math.max(...languages.map((language) => SENTENCE_WORD_LIMIT[language]));
    const language = languages.length === 1 ? languages[0] : 'any';
    return splitSentences(text).flatMap((sentence, index) => {
        const words = tokenize(sentence).length;
        return words > limit ? [{ id: `long-sentence:${index}`, rule: 'long-sentence' as const, language, words, limit }] : [];
    });
}

// ---------------------------------------------------------------------------
// Passive voice
// ---------------------------------------------------------------------------

const NL_WORDEN = new Set(['word', 'wordt', 'worden', 'werd', 'werden']);
const NL_ZIJN = new Set(['is', 'zijn', 'ben', 'bent', 'was', 'waren']);

/**
 * Participles used as a state or with an active perfect ("bent u getrouwd",
 * "is geboren", "bent u verhuisd"), never flagged.
 */
const NL_STATE_PARTICIPLES = new Set([
    'geboren',
    'getrouwd',
    'gehuwd',
    'gescheiden',
    'overleden',
    'gestorven',
    'verhuisd',
    'verloofd',
    'verplicht',
    'bekend',
    'gewend',
    'geïnteresseerd',
    'gepensioneerd',
    'gestopt',
    'geweest',
    'geworden',
    'gebleven',
    'begonnen',
    'gekomen',
    'gegaan',
    'gebeurd',
    'gelukt',
    'verzekerd',
    'ingeschreven',
    'gevestigd',
    'bevoegd',
    'gerechtigd',
    'gehandicapt',
    'gevaccineerd',
    'tevreden',
    'betrokken',
    'verbonden',
    'vergeten',
    'geslaagd',
    'gezakt'
]);

/** Words shaped like a participle that are nouns or adjectives. */
const NL_NOT_PARTICIPLES = new Set([
    'geslacht',
    'gewicht',
    'gezicht',
    'gebied',
    'geld',
    'geluid',
    'gedicht',
    'gerecht',
    'gevecht',
    'gezond',
    'geduld',
    'gebed',
    'gebit',
    'gedrag',
    'gemeenschap',
    'bericht',
    'beleid',
    'verband',
    'verbod',
    'verschuldigd',
    'verkeerd',
    'vertrouwd',
    'gericht',
    'geschikt',
    'gelijkwaardig',
    'gewest',
    'verleden',
    'gevaar',
    'ervaren',
    'bekwaam',
    'herfst',
    'ontbijt',
    'verlof',
    'bezit',
    'bereid',
    'gesprek'
]);

/**
 * Participles of transitive verbs common in forms. With *zijn* only these
 * count as passive ("is verzonden", "zijn ontvangen"): *zijn* + participle is
 * also the active perfect and the state reading, so we stay with known verbs.
 */
const NL_KNOWN_PARTICIPLES = new Set([
    'ingevuld',
    'verzonden',
    'verstuurd',
    'ontvangen',
    'gevraagd',
    'gebruikt',
    'verwerkt',
    'opgeslagen',
    'gedeeld',
    'bewaard',
    'verwijderd',
    'gecontroleerd',
    'beoordeeld',
    'behandeld',
    'goedgekeurd',
    'afgewezen',
    'aangevraagd',
    'toegestuurd',
    'opgestuurd',
    'teruggestuurd',
    'betaald',
    'verstrekt',
    'gegeven',
    'genomen',
    'gemaakt',
    'gedaan',
    'aangeboden',
    'geleverd',
    'bevestigd',
    'uitgevoerd',
    'ondertekend',
    'vermeld',
    'aangegeven',
    'ingediend',
    'doorgestuurd',
    'gemeld',
    'gewijzigd',
    'aangepast',
    'bijgewerkt',
    'toegevoegd',
    'berekend',
    'vastgesteld',
    'verzocht',
    'beantwoord',
    'gelezen',
    'geschreven',
    'besproken',
    'gestuurd',
    'geregeld',
    'geannuleerd',
    'afgerond',
    'verlengd',
    'toegekend',
    'uitbetaald',
    'overgemaakt',
    'geplaatst',
    'gepubliceerd',
    'geselecteerd',
    'gekozen',
    'gevonden',
    'gezien',
    'gesloten',
    'gebracht',
    'onderzocht',
    'bekeken',
    'beschreven',
    'toegezonden',
    'gehouden',
    'bijgehouden',
    'opgenomen',
    'doorgegeven',
    'opgegeven',
    'vastgelegd',
    'uitgenodigd',
    'gebeld',
    'gemaild',
    'geïnformeerd',
    'benaderd',
    'verwacht',
    'geacht',
    'geweigerd',
    'ingetrokken',
    'gecorrigeerd',
    'geactiveerd',
    'geregistreerd'
]);

const NL_SEPARABLE = '(?:aan|af|bij|door|in|mee|na|om|onder|op|over|terug|toe|uit|voor|weg|vast|samen|neer|binnen|buiten|tegen)';
// Weak participles: (separable prefix +) ge…d/t, or an unstressed prefix + …d/t.
const NL_WEAK_PARTICIPLE = new RegExp(`^(?:${NL_SEPARABLE}?ge\\p{L}{2,}|(?:be|ver|ont|her)\\p{L}{3,})[dt]$`, 'u');

function isDutchParticiple(word: string, strict: boolean): boolean {
    if (NL_STATE_PARTICIPLES.has(word)) return false;
    if (NL_KNOWN_PARTICIPLES.has(word)) return true;
    if (strict || NL_NOT_PARTICIPLES.has(word)) return false;
    return NL_WEAK_PARTICIPLE.test(word);
}

const EN_BE = new Set(['am', 'is', 'are', 'was', 'were', 'be', 'been', 'being']);
// One adverb may sit between *be* and the participle: "will be securely stored".
const EN_ADVERBS = new Set(['not', 'also', 'then', 'already', 'always', 'usually', 'often', 'never', 'only', 'automatically', 'securely', 'still', 'now', 'just', 'safely', 'currently', 'normally']);

/** -ed words that describe a state, or are not participles at all. */
const EN_NOT_PASSIVE = new Set([
    'married',
    'divorced',
    'widowed',
    'separated',
    'retired',
    'employed',
    'unemployed',
    'interested',
    'tired',
    'bored',
    'worried',
    'concerned',
    'satisfied',
    'dissatisfied',
    'pleased',
    'excited',
    'scared',
    'frightened',
    'prepared',
    'qualified',
    'registered',
    'based',
    'located',
    'situated',
    'related',
    'involved',
    'supposed',
    'used',
    'aged',
    'named',
    'called',
    'disabled',
    'vaccinated',
    'insured',
    'licensed',
    'certified',
    'allowed',
    'engaged',
    'experienced',
    'skilled',
    'advanced',
    'detailed',
    'limited',
    'complicated',
    'crowded',
    'closed',
    'finished',
    'hundred',
    'naked',
    'wicked',
    'sacred',
    'rugged',
    'beloved',
    'kindred',
    'infrared',
    'confused',
    'surprised',
    'disappointed',
    'annoyed',
    'relaxed',
    'determined',
    'dedicated',
    'committed',
    'self-employed',
    'covered',
    'enrolled',
    'subscribed',
    'logged'
]);

const EN_IRREGULAR_PARTICIPLES = new Set([
    'sent',
    'given',
    'taken',
    'made',
    'written',
    'seen',
    'paid',
    'sold',
    'held',
    'kept',
    'told',
    'shown',
    'found',
    'chosen',
    'built',
    'bought',
    'brought',
    'caught',
    'spent',
    'drawn',
    'driven',
    'forgiven',
    'hidden',
    'broken',
    'spoken',
    'stolen',
    'thrown',
    'withdrawn',
    'undertaken',
    'understood',
    'upheld',
    'withheld',
    'meant',
    'taught',
    'sought',
    'led',
    'bound',
    'struck',
    'overseen',
    'rewritten',
    'forbidden'
]);

function isEnglishParticiple(word: string): boolean {
    if (EN_NOT_PASSIVE.has(word)) return false;
    if (EN_IRREGULAR_PARTICIPLES.has(word)) return true;
    return /^[a-z]{3,}ed$/.test(word) && !word.endsWith('eed');
}

function phrase(words: string[], from: number, to: number): string {
    const [start, end] = from <= to ? [from, to] : [to, from];
    return end - start <= 4 ? words.slice(start, end + 1).join(' ') : `${words[start]} … ${words[end]}`;
}

const NL_HEBBEN = new Set(['heb', 'hebt', 'heeft', 'hebben', 'had', 'hadden']);
// A participle belongs to the verb of its own clause: "Wat zijn de kosten |
// die u heeft gemaakt?" is not passive. Split at conjunctions and relative
// words that open a new clause ("dat"/"wat" are left alone: too ambiguous).
const NL_CLAUSE_OPENERS = new Set(['die', 'en', 'maar', 'of', 'omdat', 'zodat', 'wanneer', 'nadat', 'voordat', 'terwijl', 'als', 'indien', 'welke', 'waarin', 'waarmee', 'waarvoor', 'waarop']);

function splitDutchClauses(words: string[]): string[][] {
    const clauses: string[][] = [[]];
    for (const word of words) {
        if (NL_CLAUSE_OPENERS.has(word.toLowerCase()) && clauses[clauses.length - 1].length) clauses.push([]);
        clauses[clauses.length - 1].push(word);
    }
    return clauses;
}

function passiveInClauseNl(clauseWords: string[]): string | null {
    for (const words of splitDutchClauses(clauseWords)) {
        const match = passiveInDutchWords(words);
        if (match) return match;
    }
    return null;
}

function passiveInDutchWords(words: string[]): string | null {
    const lower = words.map((word) => word.toLowerCase());
    // With *hebben* in the clause the participle is its active perfect.
    const hasHebben = lower.some((word) => NL_HEBBEN.has(word));
    for (let i = 0; i < lower.length; i += 1) {
        const isWorden = NL_WORDEN.has(lower[i]);
        if (!isWorden && (!NL_ZIJN.has(lower[i]) || hasHebben)) continue;
        // Main clause: participle at the end ("wordt … ingevuld"); subclause or
        // modal: participle before the auxiliary ("ingevuld wordt / worden").
        for (let j = 0; j < lower.length; j += 1) {
            if (j === i || Math.abs(j - i) > 8) continue;
            if (isDutchParticiple(lower[j], !isWorden)) return phrase(words, i, j);
        }
    }
    return null;
}

function passiveInClauseEn(words: string[]): string | null {
    const lower = words.map((word) => word.toLowerCase());
    for (let i = 0; i < lower.length - 1; i += 1) {
        if (!EN_BE.has(lower[i])) continue;
        let j = i + 1;
        if (EN_ADVERBS.has(lower[j]) && j + 1 < lower.length) j += 1;
        if (isEnglishParticiple(lower[j])) return phrase(words, i, j);
    }
    return null;
}

/**
 * Passive voice: Dutch *worden* or *zijn* + past participle, English *be* + past
 * participle. Deliberately conservative — states ("is getrouwd", "are you
 * married"), the active perfect ("bent u verhuisd") and possessive *zijn*
 * ("zijn adres") stay quiet. One hint per language: the first passive found.
 */
export function checkPassive(text: string, languages: PlainLanguage[]): PlainLanguageHint[] {
    const hints: PlainLanguageHint[] = [];
    for (const language of languages) {
        const find = language === 'nl' ? passiveInClauseNl : passiveInClauseEn;
        for (const sentence of splitSentences(text)) {
            const match = splitClauses(sentence)
                .map((clause) => find(tokenize(clause)))
                .find(Boolean);
            if (match) {
                hints.push({ id: `passive:${language}:${match.toLowerCase()}`, rule: 'passive', language, match });
                break;
            }
        }
    }
    return hints;
}

// ---------------------------------------------------------------------------
// Jargon
// ---------------------------------------------------------------------------

interface JargonEntry {
    terms: string[];
    suggestion: string;
}

interface CompiledJargon {
    key: string;
    pattern: RegExp;
    suggestion: string;
}

function escapeRegExp(text: string): string {
    return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function compile(entries: JargonEntry[]): CompiledJargon[] {
    return entries.map((entry) => {
        // Longest form first, so "dient u" wins over a shorter overlap.
        const alternatives = [...entry.terms]
            .sort((a, b) => b.length - a.length)
            .map((term) => escapeRegExp(term.trim()).replace(/\s+/g, '\\s+'))
            .join('|');
        return {
            key: entry.terms[0].toLowerCase(),
            // Whole words only, any case. The pipe placeholder is not a letter,
            // so it acts as a boundary and is never part of a match.
            pattern: new RegExp(`(?<![\\p{L}\\p{N}])(?:${alternatives})(?![\\p{L}\\p{N}])`, 'iu'),
            suggestion: entry.suggestion
        };
    });
}

export const JARGON: Record<PlainLanguage, CompiledJargon[]> = {
    nl: compile((jargonNl as { entries: JargonEntry[] }).entries),
    en: compile((jargonEn as { entries: JargonEntry[] }).entries)
};

/** Officialese with a plainer alternative, one hint per list entry, in text order. */
export function checkJargon(text: string, languages: PlainLanguage[]): PlainLanguageHint[] {
    const found: Array<PlainLanguageHint & { at: number }> = [];
    for (const language of languages) {
        for (const entry of JARGON[language]) {
            const match = entry.pattern.exec(text);
            if (match) found.push({ id: `jargon:${language}:${entry.key}`, rule: 'jargon', language, match: match[0], suggestion: entry.suggestion, at: match.index });
        }
    }
    return found.sort((a, b) => a.at - b.at).map(({ at: _at, ...hint }) => hint);
}

// ---------------------------------------------------------------------------
// Double questions
// ---------------------------------------------------------------------------

const AND_OR = /(?<![\p{L}])(and\s*\/\s*or|en\s*\/\s*of)(?![\p{L}])/iu;

// "…and where do you live?" — a conjunction followed by a second question
// word or a fresh question ("and do you…"). Only counted with at least three
// words before it, so "When and where…?" stays quiet.
const JOINED_QUESTION: Record<PlainLanguage, RegExp> = {
    en: /^(and)\s+(what|where|when|why|how|which|who|whom|whose|(?:do|does|did|are|were|have|has|will|would|can|could|should)\s+(?:you|we|they))$/i,
    nl: /^(en)\s+(wat|waar|wanneer|waarom|hoe|hoeveel|welke|welk|wie|(?:bent|heeft|hebt|wilt|kunt|zou|zult|gaat|doet|had|was|wil|kan)\s+(?:u|je|jij|jullie))$/i
};

function joinedQuestion(sentence: string, language: PlainLanguage): string | null {
    const words = tokenize(sentence);
    for (let i = 3; i < words.length - 1; i += 1) {
        for (const length of [3, 2]) {
            const candidate = words.slice(i, i + length).join(' ');
            if (JOINED_QUESTION[language].test(candidate)) return candidate;
        }
    }
    return null;
}

/**
 * Two questions in one: "and/or" / "en/of", two question marks, or (in a
 * question) "and" joining a second question.
 */
export function checkDoubleQuestion(text: string, languages: PlainLanguage[]): PlainLanguageHint[] {
    const hints: PlainLanguageHint[] = [];
    const andOr = AND_OR.exec(text);
    if (andOr) hints.push({ id: 'double-question:and-or', rule: 'double-question', language: 'any', match: andOr[0], variant: 'and-or' });

    // Count question marks that end a run of words: "Why??" is one question.
    const questions = text
        .split(/\?+/)
        .slice(0, -1)
        .filter((part) => tokenize(part).length > 0);
    if (questions.length >= 2) {
        hints.push({ id: 'double-question:two-question-marks', rule: 'double-question', language: 'any', variant: 'two-question-marks' });
        return hints;
    }

    if (text.includes('?')) {
        for (const language of languages) {
            const sentence = splitSentences(text).find((part) => part.includes('?'));
            const match = sentence ? joinedQuestion(sentence, language) : null;
            if (match) {
                hints.push({ id: `double-question:joined:${language}`, rule: 'double-question', language, match, variant: 'joined-questions' });
                break;
            }
        }
    }
    return hints;
}
