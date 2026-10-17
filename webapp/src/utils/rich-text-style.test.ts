import { describe, expect, it } from 'vitest';

import { isValidColor, isValidFontSize, sanitiseRichText, styleValueProblem } from '@app/utils/rich-text-style';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/get-html-from-json';

// Same values as backend tests/app/services/test_rich_text_style.py.
describe('rich-text style values', () => {
    it.each(['12', '15', '16', '24', '32', '16px', '8px', '96', '13.5px'])('keeps the font size %s', (value) => expect(isValidFontSize(value)).toBe(true));
    it.each(['', '7px', '97px', '1em', '16 px', '16px;color:red', 'calc(1px)', '-12px', 16, null])('refuses the font size %s', (value) => expect(isValidFontSize(value)).toBe(false));
    it.each(['#fff', '#A0b1C2', 'rgb(255, 0, 0)', 'rgb(0,0,0)', 'rgba(0, 0, 0, 0.5)', 'rgba(1,2,3,1)', 'rgba(1,2,3,.25)'])('keeps the colour %s', (value) => expect(isValidColor(value)).toBe(true));
    it.each(['red', '#ff00', '#gggggg', 'rgb(256, 0, 0)', 'rgba(0,0,0,2)', 'rgb(1,2)', '#fff;x:y', 'url(x)', 'var(--c)', '#fff\n', 'rgb(1,\t2,3)', 'rgb(1,\u00a02,3)', 'rgb(\u0661,2,3)', 0])('refuses the colour %s', (value) =>
        expect(isValidColor(value)).toBe(false)
    );
    it.each(['12px\n', '12\n', '\u0661\u0662px'])('refuses the font size %j like the backend', (value) => expect(isValidFontSize(value)).toBe(false));
    it('takes null as no value', () => {
        expect(styleValueProblem('fontSize', null)).toBeNull();
        expect(styleValueProblem('color', null)).toBeNull();
    });
});

const title = (attrs: Record<string, unknown>) => ({
    type: 'doc',
    content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Hi', marks: [{ type: 'textStyle', attrs }] }] }]
});

describe('sanitising a stored title', () => {
    it('drops unusable values and keeps the rest, without changing the input', () => {
        const stored = title({ fontSize: '12px; background: url(x)', color: '#ff0000' });
        expect(sanitiseRichText(stored)).toEqual(title({ color: '#ff0000' }));
        expect(stored.content[0].content[0].marks[0].attrs.fontSize).toBe('12px; background: url(x)');
    });

    it('never renders an unusable value into the style attribute', () => {
        const html = getHtmlFromJson(title({ fontSize: '24px', color: 'red; position: fixed' }) as any) ?? '';
        expect(html).toContain('font-size: 24px');
        expect(html).not.toContain('position');
        expect(html).not.toContain('red');
    });
});
