// The label a pipe chip stores in a question's title is part of the form (respondents' pages read it back): it is
// made in English whatever language the creator works in; only the menu shows the builder's language.
import i18n from 'i18next';
import { afterEach, describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';

import { buildPipeItems } from './index';

const field = (id: string, index: number, title: string): StandardFormFieldDto => ({ id, index, type: FieldTypes.SHORT_TEXT, title }) as StandardFormFieldDto;
const page = (id: string, index: number, fields: StandardFormFieldDto[]): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, properties: { fields } }) as StandardFormFieldDto;

const first = field('a', 0, 'Naam');
const second = field('b', 0, 'E-mail');
const target = field('c', 1, 'Hallo');
const pages = [page('p1', 0, [first]), page('p2', 1, [second, target])];
const items = () => buildPipeItems(pages, ['bron'], target, pages[1]);

afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('answer pipe labels', () => {
    it('shows and stores the same label in English', () => {
        expect(items().map((item) => [item.label, item.storedLabel])).toEqual([
            ['Page 1 · Naam', 'Page 1 · Naam'],
            ['Page 2 · E-mail', 'Page 2 · E-mail'],
            ['bron', undefined]
        ]);
    });

    it('stores the English label while the menu is Dutch', async () => {
        await i18n.changeLanguage('nl');
        const dutch = items();
        expect(dutch.map((item) => item.label)).toEqual(['Pagina 1 · Naam', 'Pagina 2 · E-mail', 'bron']);
        expect(dutch.map((item) => item.storedLabel)).toEqual(['Page 1 · Naam', 'Page 2 · E-mail', undefined]);
    });
});
