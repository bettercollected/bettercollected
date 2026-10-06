import { describe, expect, it } from 'vitest';

import { PIPE, SENTENCE_WORD_LIMIT, checkDoubleQuestion, checkJargon, checkPassive, checkPlainLanguage, checkSentenceLength, detectLanguage, languagesToCheck, normalizeFormLanguage, plainTextForCheck } from './index';
import { JARGON } from './rules';

const words = (count: number, word = 'woord') => Array.from({ length: count }, () => word).join(' ');
const rules = (text: string, formLanguage?: string) => checkPlainLanguage(text, { formLanguage }).map((hint) => hint.rule);

describe('sentence length', () => {
    it('uses 20 words for Dutch and 25 for English', () => {
        expect(SENTENCE_WORD_LIMIT).toEqual({ nl: 20, en: 25 });
    });

    it('flags a Dutch sentence over 20 words', () => {
        const [hint] = checkSentenceLength(`${words(21)}.`, ['nl']);
        expect(hint).toMatchObject({ rule: 'long-sentence', language: 'nl', words: 21, limit: 20 });
    });

    it('does not flag a Dutch sentence of exactly 20 words', () => {
        expect(checkSentenceLength(`${words(20)}.`, ['nl'])).toEqual([]);
    });

    it('flags an English sentence over 25 words but not one of 22', () => {
        expect(checkSentenceLength(`${words(26, 'word')}.`, ['en'])).toHaveLength(1);
        expect(checkSentenceLength(`${words(22, 'word')}.`, ['en'])).toEqual([]);
    });

    it('measures each sentence separately', () => {
        expect(checkSentenceLength(`${words(15)}. ${words(15)}.`, ['nl'])).toEqual([]);
        const hints = checkSentenceLength(`${words(5)}. ${words(22)}?`, ['nl']);
        expect(hints).toHaveLength(1);
        expect(hints[0].id).toBe('long-sentence:1');
    });

    it('treats paragraphs as separate sentences', () => {
        expect(checkSentenceLength(`${words(15)}\n${words(15)}`, ['nl'])).toEqual([]);
    });

    it('uses the more lenient limit when the language is unknown', () => {
        expect(checkSentenceLength(`${words(22)}.`, ['nl', 'en'])).toEqual([]);
        expect(checkSentenceLength(`${words(26)}.`, ['nl', 'en'])[0]).toMatchObject({ language: 'any', limit: 25 });
    });

    it('counts a real Dutch title end to end', () => {
        const title = 'Wilt u hieronder aangeven op welke dagen van de week en op welke tijden u in de komende periode beschikbaar bent voor een gesprek met een van onze medewerkers?';
        expect(rules(title)).toContain('long-sentence');
        expect(rules('Op welke dagen bent u beschikbaar?')).not.toContain('long-sentence');
    });
});

describe('passive voice — Dutch', () => {
    const passive = (text: string) => checkPassive(text, ['nl']);

    it.each([
        ['Het formulier wordt ingevuld door de aanvrager.', 'wordt ingevuld'],
        ['Is uw aanvraag verzonden?', 'Is uw aanvraag verzonden'],
        ['Welke gegevens worden gevraagd?', 'worden gevraagd'],
        ['Uw gegevens worden bewaard voor onderzoek.', 'worden bewaard'],
        ['Dit veld moet worden ingevuld.', 'worden ingevuld'],
        ['Hoe vaak werd u gebeld?', 'werd u gebeld'],
        ['De documenten zijn ontvangen.', 'zijn ontvangen']
    ])('flags "%s"', (text, match) => {
        expect(passive(text)).toEqual([expect.objectContaining({ rule: 'passive', language: 'nl', match })]);
    });

    it.each([
        ['Bent u getrouwd?'],
        ['Is uw partner getrouwd of gescheiden?'],
        ['Waar bent u geboren?'],
        ['Bent u verhuisd in de afgelopen twee jaar?'],
        ['Wat is zijn adres?'],
        ['Zijn ouders wonen in Utrecht.'],
        ['Wat is uw geslacht?'],
        ['Wat is uw gewicht in kilo?'],
        ['Wat zijn de kosten die u heeft gemaakt?'],
        ['Bent u ingeschreven bij de gemeente?'],
        ['Wat is uw e-mailadres?'],
        ['Hoe tevreden bent u over ons?']
    ])('does not flag "%s"', (text) => {
        expect(passive(text)).toEqual([]);
    });
});

describe('passive voice — English', () => {
    const passive = (text: string) => checkPassive(text, ['en']);

    it.each([
        ['A photo is required.', 'is required'],
        ['Your receipt will be sent by email.', 'be sent'],
        ['Your data is securely stored in the EU.', 'is securely stored'],
        ['Has your form been approved?', 'been approved'],
        ['These answers are shared with your manager.', 'are shared']
    ])('flags "%s"', (text, match) => {
        expect(passive(text)).toEqual([expect.objectContaining({ rule: 'passive', language: 'en', match })]);
    });

    it.each([
        ['Are you married?'],
        ['Is your partner employed?'],
        ['We are interested in your opinion.'],
        ['What is your company called?'],
        ['Where are you based?'],
        ['What do you need?'],
        ['Is the shop closed on Sundays?'],
        ['We will send you a receipt.']
    ])('does not flag "%s"', (text) => {
        expect(passive(text)).toEqual([]);
    });
});

describe('jargon', () => {
    it('has 40–60 entries per language', () => {
        expect(JARGON.nl.length).toBeGreaterThanOrEqual(40);
        expect(JARGON.nl.length).toBeLessThanOrEqual(60);
        expect(JARGON.en.length).toBeGreaterThanOrEqual(40);
        expect(JARGON.en.length).toBeLessThanOrEqual(60);
    });

    it('suggests a plain Dutch alternative', () => {
        expect(checkJargon('Indien u vragen heeft, kunt u bellen.', ['nl'])).toEqual([expect.objectContaining({ rule: 'jargon', match: 'Indien', suggestion: 'als' })]);
        expect(checkJargon('U dient te betalen middels iDEAL.', ['nl']).map((hint) => hint.match)).toEqual(['dient te', 'middels']);
        expect(checkJargon('Waar bent u woonachtig?', ['nl'])[0]).toMatchObject({ suggestion: expect.stringContaining('wonen') });
    });

    it('matches Dutch multi-word terms across any whitespace and in any case', () => {
        expect(checkJargon('Ten  Behoeve van het onderzoek', ['nl'])[0]).toMatchObject({ match: 'Ten  Behoeve van', suggestion: 'voor' });
    });

    it('suggests a plain English alternative', () => {
        expect(checkJargon('Please furnish your address in order to receive the pack.', ['en']).map((hint) => [hint.match, hint.suggestion])).toEqual([
            ['furnish', 'give'],
            ['in order to', 'to']
        ]);
        expect(checkJargon('UTILISE the form prior to Monday.', ['en']).map((hint) => hint.suggestion)).toEqual(['use', 'before']);
    });

    it('only matches whole words', () => {
        expect(checkJargon('Wat is uw thansnummer of reedsje?', ['nl'])).toEqual([]);
        expect(checkJargon('Commencement', ['en'])).toHaveLength(1);
        expect(checkJargon('Our recommence button', ['en'])).toEqual([]);
        expect(checkJargon('Is the windowsill sufficiently wide?', ['en'])).toEqual([]);
    });

    it('does not flag plain text', () => {
        expect(checkJargon('Als u vragen heeft, belt u ons.', ['nl'])).toEqual([]);
        expect(checkJargon('Use this form to tell us about the start date.', ['en'])).toEqual([]);
    });
});

describe('double questions', () => {
    it('flags and/or and en/of', () => {
        expect(checkDoubleQuestion('Heeft u een auto en/of een fiets?', ['nl'])[0]).toMatchObject({ variant: 'and-or', match: 'en/of' });
        expect(checkDoubleQuestion('Do you own a car and/or a bike?', ['en'])[0]).toMatchObject({ variant: 'and-or', match: 'and/or' });
    });

    it('flags two question marks', () => {
        expect(checkDoubleQuestion('Wat is uw naam? En wat is uw adres?', ['nl'])[0]).toMatchObject({ variant: 'two-question-marks' });
        expect(checkDoubleQuestion('How old are you? Where do you live?', ['en'])[0]).toMatchObject({ variant: 'two-question-marks' });
    });

    it('flags a second question joined with "and" / "en"', () => {
        expect(checkDoubleQuestion('Wat is uw naam en waar woont u?', ['nl'])[0]).toMatchObject({ variant: 'joined-questions', match: 'en waar' });
        expect(checkDoubleQuestion('How old are you and do you smoke?', ['en'])[0]).toMatchObject({ variant: 'joined-questions', match: 'and do you' });
    });

    it.each([
        ['Wat is uw naam en adres?'],
        ['Wanneer en waar bent u geboren?'],
        ['Welke kleuren en maten wilt u?'],
        ['Why??'],
        ['What is your name and address?'],
        ['When and where did it happen?'],
        ['Tell us about your skills and what you would like to learn.']
    ])('does not flag "%s"', (text) => {
        expect(checkDoubleQuestion(text, ['nl', 'en'])).toEqual([]);
    });
});

describe('pipe tokens', () => {
    const title = (...content: object[]) => ({ type: 'doc', content: [{ type: 'paragraph', content }] });
    const pipe = (label: string) => ({ type: 'answerPipe', attrs: { kind: 'field', pipeKey: 'f1', label } });

    it('reads TipTap titles as plain text with pipes masked', () => {
        expect(plainTextForCheck(title({ type: 'text', text: 'Hallo ' }, pipe('Indien'), { type: 'text', text: ', hoe gaat het?' }))).toBe(`Hallo ${PIPE}, hoe gaat het?`);
    });

    it('never flags a pipe chip label as jargon', () => {
        expect(checkPlainLanguage(title({ type: 'text', text: 'Wat vindt u van ' }, pipe('middels'), { type: 'text', text: '?' }))).toEqual([]);
    });

    it('masks {{field:…}} / {{hidden:…}} tokens and @mentions in plain text', () => {
        expect(plainTextForCheck('Beste {{hidden:naam|klant}}, wat vindt u van @indien?')).toBe(`Beste ${PIPE}, wat vindt u van ${PIPE}?`);
        expect(checkPlainLanguage('Beste {{field:middels}}, hoe gaat het met @teneinde?')).toEqual([]);
    });

    it('keeps e-mail addresses as text', () => {
        expect(plainTextForCheck('Mail ons op info@voorbeeld.nl')).toBe('Mail ons op info@voorbeeld.nl');
    });

    it('counts a pipe as one word for sentence length', () => {
        const text = `${words(20)} {{field:abc}}.`;
        expect(checkSentenceLength(plainTextForCheck(text), ['nl'])[0]).toMatchObject({ words: 21 });
    });

    it('accepts a JSON-encoded title string', () => {
        expect(plainTextForCheck(JSON.stringify(title({ type: 'text', text: 'Waar bent u woonachtig?' })))).toBe('Waar bent u woonachtig?');
    });
});

describe('language detection', () => {
    it.each([
        ['Wat is uw naam en waar woont u?', 'nl'],
        ['Hoeveel kinderen heeft u?', 'nl'],
        ['Wilt u een kopie van de antwoorden ontvangen?', 'nl'],
        ['What is your name and where do you live?', 'en'],
        ['How many children do you have?', 'en'],
        ['Would you like a copy of your answers?', 'en']
    ])('detects "%s" as %s', (text, language) => {
        expect(detectLanguage(text)).toBe(language);
    });

    it.each([['Naam'], ['E-mail'], ['Is het OK?'], ['']])('is unsure about "%s"', (text) => {
        expect(detectLanguage(text)).toBe('unknown');
    });

    it('prefers the form language when it names Dutch or English', () => {
        expect(normalizeFormLanguage('nl-NL')).toBe('nl');
        expect(normalizeFormLanguage('Dutch')).toBe('nl');
        expect(normalizeFormLanguage('en_GB')).toBe('en');
        expect(normalizeFormLanguage('de')).toBeNull();
        expect(languagesToCheck('What is your name?', 'nl')).toEqual(['nl']);
        expect(languagesToCheck('Wat is uw naam?', 'fr')).toEqual(['nl']);
    });

    it('checks both languages when unsure', () => {
        expect(languagesToCheck('Naam')).toEqual(['nl', 'en']);
        // "Indien" is Dutch officialese; a one-word title still gets the hint.
        expect(rules('Indien?')).toEqual(['jargon']);
    });
});

describe('checkPlainLanguage', () => {
    it('returns nothing for empty or plain titles', () => {
        expect(checkPlainLanguage(null)).toEqual([]);
        expect(checkPlainLanguage('Wat is uw naam?')).toEqual([]);
        expect(checkPlainLanguage('What is your name?')).toEqual([]);
    });

    it('combines rules with stable ids', () => {
        const hints = checkPlainLanguage('Indien u verhuist, dient te worden aangegeven waar u woonachtig bent en/of wanneer?');
        expect(hints.map((hint) => hint.rule)).toEqual(['jargon', 'jargon', 'jargon', 'passive', 'double-question']);
        expect(hints.map((hint) => hint.id)).toEqual(['jargon:nl:indien', 'jargon:nl:dient te', 'jargon:nl:woonachtig', 'passive:nl:worden aangegeven', 'double-question:and-or']);
    });
});
