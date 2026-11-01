import { describe, expect, it } from 'vitest';

import { SIGNATURE_NAME_MAX, answerSignature, isPlainImageId, isSignatureName, isSigned, normalisedName, signatureExportText, signatureNameLength, signatureProblem, signatureShape } from './signature';

describe('typed names (the server twin is common signature.py)', () => {
    it.each(['Fatima El Idrissi', '李小龙', 'Zoë', 'O’Brien-Smith', 'x'.repeat(SIGNATURE_NAME_MAX)])('accepts %s', (name) => {
        expect(isSignatureName(name)).toBe(true);
        expect(signatureProblem({ method: 'typed', name })).toBeNull();
    });

    it.each([
        ['empty', ''],
        ['a leading space', ' Ada'],
        ['a trailing space', 'Ada '],
        ['a zero-width space inside', 'a​b'],
        ['a right-to-left override', 'a‮b'],
        ['a line break', 'a\nb'],
        ['a tab', 'a\tb'],
        ['a decomposed accent (not Unicode form C)', 'é'],
        ['the byte order mark', '﻿Ada']
    ])('refuses %s', (_why, name) => {
        expect(isSignatureName(name)).toBe(false);
        expect(signatureProblem({ method: 'typed', name })).toBe('FORMAT');
    });

    it('counts characters as the server does, by code point', () => {
        expect(signatureNameLength('a😀')).toBe(2);
        expect(signatureProblem({ method: 'typed', name: 'x'.repeat(SIGNATURE_NAME_MAX + 1) })).toBe('TOO_LONG');
        expect(signatureProblem({ method: 'typed', name: '😀'.repeat(SIGNATURE_NAME_MAX) })).toBeNull();
    });

    it('stores what was typed trimmed and in form C, and nothing for what leaves nothing or something forbidden', () => {
        expect(normalisedName('  Ada Lovelace \n')).toBe('Ada Lovelace');
        expect(normalisedName('Zoë')).toBe('Zoë');
        expect(normalisedName('   ')).toBeUndefined();
        expect(normalisedName('a​b')).toBeUndefined();
        // a name made so is one the server accepts
        expect(isSignatureName(normalisedName('  Zoë  ') as string)).toBe(true);
    });
});

describe('the answer', () => {
    it('knows its shape: text only, the keys the server keeps, an object', () => {
        expect(signatureShape({ method: 'typed', name: 'A' })).toBe(true);
        expect(signatureShape({ method: 'drawn', file_id: 'x', signed_at: '2026-11-01T10:00:00Z', url: 'https://f.example/x' })).toBe(true);
        expect(signatureShape({ method: 'typed', name: 'A', extra: 'x' })).toBe(false);
        expect(signatureShape({ method: 'typed', name: 7 })).toBe(false);
        expect(signatureShape('Fatima')).toBe(false);
        expect(signatureShape(['A'])).toBe(false);
        expect(signatureShape(null)).toBe(false);
    });

    it('breaks nothing only when the method and what goes with it fit', () => {
        expect(signatureProblem({ method: 'drawn', file_id: 'img-1' })).toBeNull();
        expect(signatureProblem({ method: 'drawn', file_id: '../x' })).toBe('SIGNATURE_IMAGE');
        expect(signatureProblem({ method: 'drawn' })).toBe('SIGNATURE_IMAGE');
        expect(signatureProblem({ method: 'drawn', file_id: 'x', name: 'A' })).toBe('FORMAT');
        expect(signatureProblem({ method: 'typed', name: 'A', file_id: 'x' })).toBe('FORMAT');
        expect(signatureProblem({ method: 'scribble', name: 'A' })).toBe('FORMAT');
        expect(signatureProblem({})).toBe('FORMAT');
    });

    it('takes only a plain id for the image', () => {
        for (const id of ['abc-1_2.png', 'a'.repeat(128)]) expect(isPlainImageId(id)).toBe(true);
        for (const id of ['', '.', '..', 'a/b', 'a b', 'a'.repeat(129), 7, null]) expect(isPlainImageId(id)).toBe(false);
    });

    it('reads the slot, and says whether a well-formed signature is there', () => {
        expect(answerSignature({ signature: { method: 'typed', name: 'A' } })).toEqual({ method: 'typed', name: 'A' });
        expect(answerSignature({ signature: 'A' })).toBeUndefined();
        expect(answerSignature(undefined)).toBeUndefined();
        expect(isSigned({ signature: { method: 'typed', name: 'A' } })).toBe(true);
        expect(isSigned({ signature: { method: 'typed', name: '' } })).toBe(false);
        expect(isSigned({})).toBe(false);
    });

    it('writes the typed name or a marker in an export, never an image or a link', () => {
        expect(signatureExportText({ signature: { method: 'typed', name: 'Ada Lovelace' } })).toBe('Ada Lovelace');
        expect(signatureExportText({ signature: { method: 'drawn', file_id: 'x', url: 'https://f.example/x?sig' } })).toBe('[drawn signature]');
        expect(signatureExportText({})).toBe('');
    });
});
