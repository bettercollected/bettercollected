/**
 * Plain-language check for question text in the form builder.
 *
 * Helps creators write at B1 level — the plain-language level the Dutch
 * government's Direct Duidelijk programme holds public communication to — in
 * Dutch and English. Rule-based and advisory: hints never block saving or
 * publishing, and a creator can dismiss any of them.
 *
 * Rules (each in ./rules.ts, all pure and cheap enough to run while typing):
 * - long sentences (SENTENCE_WORD_LIMIT: 20 words Dutch, 25 English);
 * - passive voice (worden/zijn + participle; be + participle), conservative;
 * - officialese with a plainer alternative (jargon-nl.json, jargon-en.json);
 * - double questions ("and/or", two question marks, "…and where…?").
 *
 * Language: the form's `settings.language` when it names Dutch or English,
 * otherwise a per-text guess from function words; when unsure, both rule sets
 * run (with the more lenient sentence limit).
 *
 * Design note — a later AI-assisted version (not built): it would sit behind
 * the workspace's existing AI opt-in, run only when the creator asks for a
 * rewrite, and send only the creator's own question text (title and
 * description, with pipes left as placeholders) — never other fields,
 * responses or respondent data. These rules would stay the always-on,
 * offline baseline; AI suggestions would be shown the same way, as dismissible
 * hints, and never applied without the creator accepting them.
 */
import { languagesToCheck } from './language';
import { PlainLanguageHint, checkDoubleQuestion, checkJargon, checkPassive, checkSentenceLength } from './rules';
import { plainTextForCheck } from './text';

export { detectLanguage, languagesToCheck, normalizeFormLanguage } from './language';
export type { LanguageGuess, PlainLanguage } from './language';
export { SENTENCE_WORD_LIMIT, checkDoubleQuestion, checkJargon, checkPassive, checkSentenceLength } from './rules';
export type { PlainLanguageHint, PlainLanguageRule } from './rules';
export { PIPE, plainTextForCheck } from './text';

export interface PlainLanguageOptions {
    /** The form's declared language (`settings.language`), if any. */
    formLanguage?: string | null;
}

/**
 * All plain-language hints for a title (TipTap JSON or string) or a
 * description (plain text with `{{…}}` pipe tokens). Pipes are never words.
 */
export function checkPlainLanguage(value: unknown, options: PlainLanguageOptions = {}): PlainLanguageHint[] {
    const text = plainTextForCheck(value);
    if (!text) return [];
    const languages = languagesToCheck(text, options.formLanguage);
    const hints = [...checkJargon(text, languages), ...checkPassive(text, languages), ...checkDoubleQuestion(text, languages), ...checkSentenceLength(text, languages)];
    const seen = new Set<string>();
    return hints.filter((hint) => (seen.has(hint.id) ? false : (seen.add(hint.id), true)));
}
