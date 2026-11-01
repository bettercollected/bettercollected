import { describe, expect, it } from 'vitest';

import { ADDITION_MAX, addressLine, addressLines, addressProblems, addressShape, answerAddress, canonicalNlPostcode, formLooksUpAddresses, hardProblem, hasAnyPart, isCleanText, isNlAddition, isNlHouseNumber, isNlPostcode, isOtherPostcode, lookupKey, partProblems } from './address';

const parts = (extra: Record<string, string | undefined> = {}) => {
    const base: Record<string, string | undefined> = { street: 'Keizersgracht', house_number: '12', postcode: '1015 CS', city: 'Amsterdam', country: 'NL', ...extra };
    return Object.fromEntries(Object.entries(base).filter(([, v]) => v !== undefined));
};

describe('postcodes and house numbers', () => {
    it('knows a Dutch postcode in its stored form', () => {
        for (const value of ['1015 CS', '9999 ZZ', '1000 AA']) expect(isNlPostcode(value)).toBe(true);
        for (const value of ['1015CS', '1015 cs', '0123 AB', '1015 SS', '1015 SA', '1015 SD', '1015  CS', ' 1015 CS', '1015 CS ', '101 CS', '1015 C', '1015 CSS', '١٠١٥ CS', undefined, 1015]) expect(isNlPostcode(value)).toBe(false);
    });

    it('makes a typed postcode canonical', () => {
        expect(canonicalNlPostcode('1015cs')).toBe('1015 CS');
        expect(canonicalNlPostcode(' 1015Cs ')).toBe('1015 CS');
        expect(canonicalNlPostcode('2513aa')).toBe('2513 AA');
        for (const typed of ['1015 SS', '0123 AB', '1015', 'abc', '1015  CS', '1015-CS', '', undefined, '1015CS\nx']) expect(canonicalNlPostcode(typed)).toBeUndefined();
    });

    it('knows a Dutch house number and addition', () => {
        for (const [value, ok] of [['1', true], ['12', true], ['99999', true], ['0', false], ['012', false], ['123456', false], ['12a', false], ['', false], ['١٢', false]] as const) expect(isNlHouseNumber(value)).toBe(ok);
        for (const [value, ok] of [['A', true], ['bis', true], ['2', true], ['hoog-2', true], ['1 hoog', true], ['-2', false], [' A', false], ['A ', false], ['x'.repeat(ADDITION_MAX + 1), false], ['', false], ['a;b', false]] as const) expect(isNlAddition(value)).toBe(ok);
    });

    it('knows a postcode of another country', () => {
        for (const [value, ok] of [['1000', true], ['SW1A 1AA', true], ['10115', true], ['1', false], ['-1000', false], ['1000-', false], ['1000  10', false], ['x'.repeat(13), false], ['@@', false]] as const) expect(isOtherPostcode(value)).toBe(ok);
    });

    it('turns two valid values into the lookup key and refuses anything else', () => {
        expect(lookupKey('1015cs', ' 12 ')).toEqual({ postcode: '1015CS', houseNumber: '12' });
        expect(lookupKey('1015 CS', '12')).toEqual({ postcode: '1015CS', houseNumber: '12' });
        for (const [postcode, number] of [['1015 SS', '12'], ['1015 CS', '0'], ['1015 CS', '12a'], ['', ''], [undefined, '1'], ['1015 CS OR x', '12'], ['1015 CS', '12 OR 1=1']] as const) expect(lookupKey(postcode, number)).toBeUndefined();
    });
});

describe('text rules', () => {
    it('keeps clean text', () => {
        for (const value of ['Keizersgracht', "Rue de l'Église", 'Straße', 'Å', "O'Brien Street"]) expect(isCleanText(value, 100)).toBe(true);
        for (const value of ['', ' x', 'x ', 'x\n', 'x​', 'x‮', 'x­', '﻿x', 'x y', 'é', 'x'.repeat(101), undefined, 5]) expect(isCleanText(value, 100)).toBe(false);
    });

    it('knows the shape of an address answer', () => {
        expect(addressShape({})).toBe(true);
        expect(addressShape(parts())).toBe(true);
        expect(addressShape({ street: null })).toBe(true);
        for (const bad of ['x', null, [], { floor: '3' }, { street: 12 }, { street: ['a'] }]) expect(addressShape(bad)).toBe(false);
    });

    it('applies the hard rules to any stored address', () => {
        expect(hardProblem(parts())).toBeUndefined();
        expect(hardProblem({ street: '' })).toBeUndefined();
        expect(hardProblem('x')).toBeUndefined();
        expect(hardProblem(parts({ street: 'x​' }))).toBe('format');
        expect(hardProblem(parts({ city: ' Amsterdam' }))).toBe('format');
        expect(hardProblem(parts({ street: 'x'.repeat(101) }))).toBe('too_long');
        expect(hardProblem(parts({ country: 'NLD' }))).toBe('too_long');
        expect(hardProblem(parts({ postcode: '1'.repeat(13) }))).toBe('too_long');
    });
});

describe('the rules of an answered address (twin of the server)', () => {
    it('lets a good address through', () => {
        expect(addressProblems(parts())).toEqual([]);
        expect(addressProblems(parts({ house_number_addition: 'bis' }))).toEqual([]);
        expect(addressProblems(parts({ country: undefined }))).toEqual([]);
    });

    it('says nothing about an address that is not there', () => {
        for (const value of [{}, { street: '' }, 'x', null, undefined]) expect(addressProblems(value)).toEqual([]);
    });

    it('asks for a missing part once', () => {
        expect(addressProblems(parts({ street: undefined, city: undefined, postcode: undefined }))).toEqual(['required']);
        expect(addressProblems({ country: 'NL' })).toEqual(['required']);
        expect(addressProblems(parts({ country: undefined }), ['NL', 'BE'])).toEqual(['required']);
    });

    it('holds the country to the question', () => {
        expect(addressProblems(parts({ country: 'DE', postcode: '10115' }), ['NL', 'DE'])).toEqual([]);
        expect(addressProblems(parts({ country: 'DE', postcode: '10115' }))).toEqual(['country']);
        expect(addressProblems(parts({ country: 'nl' }))).toEqual(['format']);
        expect(addressProblems(parts({ country: 'ZZ' }))).toEqual(['format']);
    });

    it('lets each country write its own forms', () => {
        expect(addressProblems(parts({ postcode: '1015CS' }))).toEqual(['format']);
        expect(addressProblems(parts({ country: 'BE', postcode: '1000' }), ['BE'])).toEqual([]);
        expect(addressProblems(parts({ country: 'BE', postcode: 'x' }), ['BE'])).toEqual(['format']);
        expect(addressProblems(parts({ country: 'BE', postcode: '1000', house_number: '12B' }), ['BE'])).toEqual([]);
        expect(addressProblems(parts({ house_number: '12B' }))).toEqual(['format']);
    });

    it('reports a rule once however many parts break it, and a long part is not also a format problem', () => {
        expect(addressProblems(parts({ postcode: 'x', house_number: 'y', street: undefined }))).toEqual(['required', 'format']);
        expect(addressProblems(parts({ street: 'x'.repeat(101) }))).toEqual(['too_long']);
        expect(addressProblems(parts({ postcode: '1'.repeat(13) }))).toEqual(['too_long']);
    });

    it('says which part breaks which rule', () => {
        expect(partProblems(parts({ postcode: '1015cs', house_number: '', city: undefined }))).toEqual({ postcode: 'format', house_number: 'required', city: 'required' });
        expect(partProblems(parts({ country: 'DE', postcode: '10115' }))).toEqual({ country: 'country' });
        expect(partProblems(parts())).toEqual({});
        expect(partProblems({})).toEqual({});
        expect(partProblems(parts({ street: 'x'.repeat(101) }))).toEqual({ street: 'too_long' });
    });

    it('answers the same as the server does for every problem it names', () => {
        // the order of first appearance and the codes are the server's (common address.problems)
        expect(addressProblems(parts({ country: 'XX', postcode: 'x', street: undefined }))).toEqual(['required', 'format']);
    });
});

describe('showing an address', () => {
    it('writes one line, with the country code unless it is NL', () => {
        expect(addressLine(parts({ house_number_addition: 'A' }))).toBe('Keizersgracht 12 A, 1015 CS Amsterdam');
        expect(addressLine(parts({ country: 'BE' }))).toBe('Keizersgracht 12, 1015 CS Amsterdam, BE');
        expect(addressLine({ street: ' X ', city: 'Y' })).toBe('X, Y');
        expect(addressLine({ country: 'BE' })).toBe('');
        expect(addressLine(null)).toBe('');
        expect(addressLine('text')).toBe('');
    });

    it('writes lines for a page, the country by name unless NL', () => {
        expect(addressLines(parts({ house_number_addition: 'A' }), (code) => code)).toEqual(['Keizersgracht 12 A', '1015 CS Amsterdam']);
        expect(addressLines(parts({ country: 'BE' }), () => 'Belgium')).toEqual(['Keizersgracht 12', '1015 CS Amsterdam', 'Belgium']);
        expect(addressLines(undefined, (code) => code)).toEqual([]);
    });

    it('reads the parts of an answer', () => {
        expect(answerAddress({ type: 'address', address: { street: 'A', house_number: 3, postcode: null } })).toEqual({ street: 'A' });
        expect(answerAddress(undefined)).toBeUndefined();
        expect(hasAnyPart({ country: 'NL' })).toBe(false);
        expect(hasAnyPart({ street: 'A' })).toBe(true);
    });
});

describe('forms that look up addresses', () => {
    const form = (field: Record<string, unknown>) => ({ fields: [{ type: 'slide', properties: { fields: [{ id: 'a', type: 'address', ...field }] } }] });
    it('says yes for a Dutch address with the lookup on, in a group too', () => {
        expect(formLooksUpAddresses(form({}))).toBe(true);
        expect(formLooksUpAddresses(form({ properties: { countries: ['BE', 'NL'] } }))).toBe(true);
        const grouped = { fields: [{ type: 'slide', properties: { fields: [{ id: 'g', type: 'group', properties: { fields: [{ id: 'a', type: 'address' }] } }] } }] };
        expect(formLooksUpAddresses(grouped)).toBe(true);
    });

    it('says no when it is off, not Dutch, internal or absent', () => {
        expect(formLooksUpAddresses(form({ properties: { addressLookup: false } }))).toBe(false);
        expect(formLooksUpAddresses(form({ properties: { countries: ['BE'] } }))).toBe(false);
        expect(formLooksUpAddresses(form({ internal: true }))).toBe(false);
        expect(formLooksUpAddresses({ fields: [] })).toBe(false);
        expect(formLooksUpAddresses(undefined)).toBe(false);
    });
});
