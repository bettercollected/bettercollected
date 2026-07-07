import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { extractTextfromJSON, getHtmlFromJson } from './get-html-from-json';

const tiptap = (text: string, marks?: any[]) => ({ type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text, ...(marks ? { marks } : {}) }] }] });

describe('getHtmlFromJson', () => {
    it('wraps plain-string titles in a bold paragraph (legacy format)', () => {
        expect(getHtmlFromJson('Hello')).toBe('<p><strong>Hello</strong></p>');
    });

    it('renders Tiptap JSON to HTML', () => {
        expect(getHtmlFromJson(tiptap('Hi there') as any)).toContain('Hi there');
    });

    it('returns null for empty input', () => {
        expect(getHtmlFromJson(undefined)).toBeNull();
        expect(getHtmlFromJson('')).toBeNull();
    });
});

describe('extractTextfromJSON', () => {
    const field = (overrides: Partial<StandardFormFieldDto>): StandardFormFieldDto => ({ id: 'f', index: 0, type: FieldTypes.SHORT_TEXT, ...overrides });

    it('strips tags from a rendered title', () => {
        expect(extractTextfromJSON(field({ title: tiptap('Plain text') as any }))).toBe('Plain text');
    });

    it('strips tags from string titles too', () => {
        expect(extractTextfromJSON(field({ title: 'Simple' }))).toBe('Simple');
    });

    it('falls back to the per-type placeholder for untitled fields', () => {
        expect(extractTextfromJSON(field({}))).toBe('Enter Question');
        expect(extractTextfromJSON(field({ type: FieldTypes.EMAIL }))).toBe('Enter Your Email Address');
        expect(extractTextfromJSON(field({ type: FieldTypes.YES_NO }))).toBe('Are you sure?');
    });

    it('renders answerPipe chips as their label, not editor syntax', () => {
        const title = {
            type: 'doc',
            content: [
                {
                    type: 'paragraph',
                    content: [
                        { type: 'text', text: 'Hello ' },
                        { type: 'answerPipe', attrs: { kind: 'field', pipeKey: 'abc', label: 'Page 1 · Name' } },
                        { type: 'text', text: ' — welcome ' },
                        { type: 'answerPipe', attrs: { kind: 'hidden', pipeKey: 'utm_source' } }
                    ]
                }
            ]
        };
        expect(extractTextfromJSON(field({ title: title as any }))).toBe('Hello Page 1 · Name — welcome utm_source');
    });

    it('separates paragraphs with a space', () => {
        const title = {
            type: 'doc',
            content: [
                { type: 'paragraph', content: [{ type: 'text', text: 'Line one' }] },
                { type: 'paragraph', content: [{ type: 'text', text: 'line two' }] }
            ]
        };
        expect(extractTextfromJSON(field({ title: title as any }))).toBe('Line one line two');
    });
});
