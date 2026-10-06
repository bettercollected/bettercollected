import { tokenize } from './text';

export type PlainLanguage = 'nl' | 'en';

/**
 * Function words that are frequent in one language and rare or absent in the
 * other. Words both languages share in spelling ("in", "is", "of", "was",
 * "door", "die", "even", "we", "over", "had", "me") are left out on purpose.
 */
const DUTCH_WORDS = new Set([
    'de',
    'het',
    'een',
    'en',
    'van',
    'ik',
    'u',
    'uw',
    'je',
    'jij',
    'jouw',
    'wij',
    'ons',
    'onze',
    'niet',
    'wat',
    'waar',
    'wanneer',
    'waarom',
    'hoe',
    'welke',
    'welk',
    'wie',
    'hoeveel',
    'met',
    'voor',
    'op',
    'aan',
    'bij',
    'dat',
    'deze',
    'dit',
    'wordt',
    'worden',
    'werd',
    'heeft',
    'hebt',
    'heb',
    'hebben',
    'ook',
    'maar',
    'om',
    'te',
    'naar',
    'er',
    'als',
    'kunt',
    'kan',
    'wilt',
    'wil',
    'moet',
    'moeten',
    'zijn',
    'bent',
    'ben',
    'uit',
    'nog',
    'geen',
    'dan',
    'zou',
    'zal',
    'graag',
    'alstublieft',
    'omdat',
    'jullie',
    'hun',
    'mij',
    'mijn',
    'ja',
    'nee',
    'tot',
    'na'
]);

const ENGLISH_WORDS = new Set([
    'the',
    'a',
    'an',
    'and',
    'to',
    'you',
    'your',
    'yours',
    'what',
    'where',
    'when',
    'why',
    'how',
    'which',
    'who',
    'whom',
    'with',
    'for',
    'on',
    'at',
    'by',
    'that',
    'this',
    'these',
    'those',
    'be',
    'been',
    'are',
    'were',
    'will',
    'has',
    'have',
    'do',
    'does',
    'did',
    'not',
    'or',
    'if',
    'can',
    'could',
    'please',
    'would',
    'should',
    'our',
    'us',
    'it',
    'its',
    'my',
    'from',
    'about',
    'any',
    'many',
    'much',
    'there',
    'their',
    'they',
    'than',
    'then',
    'also',
    'yes',
    'no',
    'because',
    'after',
    'before'
]);

export type LanguageGuess = PlainLanguage | 'unknown';

/**
 * Guess whether a short text is Dutch or English by counting function words.
 * Short or mixed texts ("Naam", "E-mail") come back 'unknown', and the caller
 * then checks both languages.
 */
export function detectLanguage(text: string): LanguageGuess {
    let nl = 0;
    let en = 0;
    for (const word of tokenize(text.toLowerCase())) {
        if (DUTCH_WORDS.has(word)) nl += 1;
        if (ENGLISH_WORDS.has(word)) en += 1;
    }
    // Dutch spelling the English lexicon lacks: "ij" (vrijwilliger, wijk).
    if (/\p{L}ij|ij\p{L}/u.test(text.toLowerCase())) nl += 1;
    if (nl >= 2 && nl > en * 2) return 'nl';
    if (en >= 2 && en > nl * 2) return 'en';
    return 'unknown';
}

/**
 * The form's declared language, if it has one we check. Forms carry an
 * optional `settings.language` (set by some imports, e.g. "nl", "nl-NL",
 * "en_GB", "Dutch"); the builder has no picker for it yet.
 */
export function normalizeFormLanguage(language: string | null | undefined): PlainLanguage | null {
    if (!language) return null;
    const value = language.trim().toLowerCase();
    if (/^(nl|nld|dut)([-_].*)?$/.test(value) || value === 'dutch' || value === 'nederlands') return 'nl';
    if (/^(en|eng)([-_].*)?$/.test(value) || value === 'english' || value === 'engels') return 'en';
    return null;
}

/** Which language rule sets to run for one text. */
export function languagesToCheck(text: string, formLanguage?: string | null): PlainLanguage[] {
    const declared = normalizeFormLanguage(formLanguage);
    if (declared) return [declared];
    const guess = detectLanguage(text);
    return guess === 'unknown' ? ['nl', 'en'] : [guess];
}
