// Every built-in theme preset meets WCAG AA contrast wherever the respondent
// form puts one of its colours on another, text included (the button and
// border colours as text, the date picker). axe cannot measure contrast in
// jsdom (no layout), so the presets are checked from their colour values here,
// and the derived text colours are checked on palettes no preset uses.
import { describe, expect, it } from 'vitest';

import { ThemeColors } from '@app/constants/theme';
import { REQUIRED_RED, mixHex } from '@app/views/molecules/theme/theme-shared';

import { AA_NON_TEXT, AA_TEXT, contrast, hexChannels, legibleOn } from './color-contrast';
import { FOCUS_RING, actionText, calendarColours, contrastKey, outlinedButtonInk, themeContrastChecks, themeContrastGuard } from './theme-contrast';

describe('contrast', () => {
    it('follows the WCAG formula', () => {
        expect(contrast('#000000', '#FFFFFF')).toBeCloseTo(21, 5);
        expect(contrast('#FFFFFF', '#000000')).toBeCloseTo(21, 5);
        expect(contrast('#767676', '#FFFFFF')).toBeCloseTo(4.54, 2);
        expect(contrast('#1649E2', '#1649E2')).toBe(1);
    });

    it('reads short and long hex, with or without #, and ignores an alpha pair', () => {
        expect(hexChannels('#fff')).toEqual([255, 255, 255]);
        expect(hexChannels('0B3D91')).toEqual([11, 61, 145]);
        expect(hexChannels('#0B3D9126')).toEqual([11, 61, 145]);
        expect(contrast('#000', '#fff')).toBeCloseTo(21, 5);
    });

    it('fails every check for a colour it cannot read', () => {
        expect(hexChannels('white')).toBeNull();
        expect(contrast('white', '#000000') >= AA_NON_TEXT).toBe(false);
        expect(
            themeContrastChecks({ primary: 'rgb(0,0,0)', secondary: '#1649E2', tertiary: '#818CA0', accent: '#FFFFFF' })
                .filter((check) => !check.passes)
                .map((check) => check.key)
        ).toEqual(['text', 'answer']);
    });
});

describe('legibleOn', () => {
    it('keeps a colour that already reads at the minimum', () => {
        expect(legibleOn('#1649E2', '#F5F7FB', '#101828')).toBe('#1649E2');
    });

    it('moves a colour towards the ink only as far as it needs', () => {
        const weekday = legibleOn('#818CA0', '#F5F7FB', '#101828');
        expect(contrast(weekday, '#F5F7FB')).toBeGreaterThanOrEqual(AA_TEXT);
        expect(contrast(weekday, '#F5F7FB')).toBeLessThan(6);
        expect(weekday).not.toBe('#101828');
    });

    it('falls back to black or white when the ink does not read either', () => {
        expect(legibleOn('#FFFF00', '#FFFFFF', '#EEEEEE')).toBe('#000000');
        expect(legibleOn('#333333', '#000000', '#111111')).toBe('#FFFFFF');
        expect(legibleOn('teal', '#FFFFFF', 'navy')).toBe('#000000');
    });
});

describe('themeContrastChecks', () => {
    it('names the failing pairings of a palette', () => {
        const pale = { primary: '#9CA3AF', secondary: '#FDE68A', tertiary: '#E5E7EB', accent: '#FFFFFF' };
        expect(
            themeContrastChecks(pale)
                .filter((check) => !check.passes)
                .map((check) => check.key)
        ).toEqual(['text', 'answer', 'button', 'border', 'action']);
    });

    it('covers every place a theme colour is text, the border colour included', () => {
        const keys = themeContrastChecks(ThemeColors[0]).map((check) => check.key);
        expect(keys).toEqual(expect.arrayContaining(['text', 'answer', 'button', 'action-text', 'action-text-on-white', 'calendar-day', 'calendar-weekday', 'calendar-today', 'calendar-selected', 'calendar-nav', 'calendar-focus']));
    });
});

// Stored themes can hold any colours: the derived text colours read on all of them.
const AWKWARD: Array<[string, { primary: string; secondary: string; tertiary: string; accent: string }]> = [
    ['pale on white', { primary: '#9CA3AF', secondary: '#FDE68A', tertiary: '#E5E7EB', accent: '#FFFFFF' }],
    ['light ink on dark', { primary: '#F9FAFB', secondary: '#60A5FA', tertiary: '#374151', accent: '#111827' }],
    ['mid grey ground', { primary: '#777777', secondary: '#888888', tertiary: '#999999', accent: '#808080' }],
    ['saturated ground', { primary: '#FFFFFF', secondary: '#FF0000', tertiary: '#00FF00', accent: '#0000FF' }],
    ['not hex', { primary: 'black', secondary: 'rgb(0, 0, 255)', tertiary: '', accent: '#FAFAFA' }]
];

describe.each(AWKWARD)('derived text colours on a stored %s theme', (_name, theme) => {
    it.each(
        themeContrastChecks(theme as any)
            .filter((check) => check.kind === 'derived')
            .map((check) => [check.label, check] as const)
    )('%s', (_label, check) => {
        expect(check.ratio).toBeGreaterThanOrEqual(check.minimum);
    });
});

describe('the date picker keeps a theme that already passes as it was', () => {
    it.each(ThemeColors.map((theme) => [theme.title, theme] as const))('%s', (_title, theme) => {
        const colours = calendarColours(theme);
        if (contrast(theme.secondary, theme.accent) >= AA_TEXT) expect(colours.day).toBe(theme.secondary);
        if (contrast(theme.tertiary, theme.accent) >= AA_TEXT) expect(colours.weekday).toBe(theme.tertiary);
        expect(colours.background).toBe(theme.accent);
        expect(colours.selectedBackground).toBe(theme.secondary);
        expect(colours.focus).toBe(FOCUS_RING);
        expect(actionText(theme)).toBe(contrast(theme.secondary, theme.accent) >= AA_TEXT ? theme.secondary : colours.day);
    });
});

describe('the date picker focus ring', () => {
    it('keeps the app blue where it reaches 3:1 on the calendar', () => {
        expect(calendarColours({ primary: '#101828', secondary: '#1649E2', tertiary: '#818CA0', accent: '#FFFFFF' }).focus).toBe(FOCUS_RING);
    });

    it.each([
        ['a dark palette', { primary: '#F1F5F9', secondary: '#60A5FA', tertiary: '#94A3B8', accent: '#0F172A' }],
        ['a dark page with no text colour', { secondary: '#60A5FA', accent: '#0F172A' }],
        ['a navy page', { primary: '#FFFFFF', secondary: '#FFFFFF', tertiary: '#FFFFFF', accent: '#0B1F66' }]
    ])('moves the blue towards the ink on %s until it reaches 3:1', (_name, theme) => {
        expect(contrast(FOCUS_RING, theme.accent)).toBeLessThan(AA_NON_TEXT);
        const { focus, background } = calendarColours(theme);
        expect(background).toBe(theme.accent);
        expect(focus).not.toBe(FOCUS_RING);
        expect(contrast(focus, background)).toBeGreaterThanOrEqual(AA_NON_TEXT);
    });
});

describe.each(ThemeColors.map((theme) => [theme.title, theme] as const))('the %s preset', (_title, theme) => {
    it.each(themeContrastChecks(theme).map((check) => [check.label, check] as const))('%s', (_label, check) => {
        expect(check.ratio).toBeGreaterThanOrEqual(check.minimum);
    });

    it('keeps the ink legible on a chosen option (a 10% tint of the button colour)', () => {
        expect(contrast(theme.primary, mixHex(theme.secondary, theme.accent, 26 / 255))).toBeGreaterThanOrEqual(AA_TEXT);
    });

    it('shows the error icon and the submit error on the background', () => {
        expect(contrast(REQUIRED_RED, theme.accent)).toBeGreaterThanOrEqual(AA_NON_TEXT); // question-wrapper error icon
        expect(contrast('#B42318', theme.accent)).toBeGreaterThanOrEqual(AA_TEXT); // form-slide submit error
    });
});

describe('themeContrastGuard', () => {
    const passesEverything = (theme: Parameters<typeof themeContrastGuard>[0]) => themeContrastGuard(theme).issues.length === 0;

    it.each(ThemeColors.map((theme) => [theme.title, theme] as const))('lets the %s preset through untouched', (_title, theme) => {
        expect(themeContrastGuard(theme)).toEqual({ issues: [], fix: null, imageGround: false });
    });

    it('names each failing pairing once, at its worst ratio', () => {
        const { issues } = themeContrastGuard({ primary: '#9CA3AF', secondary: '#FDE68A', tertiary: '#E5E7EB', accent: '#FFFFFF' });
        expect(issues.map((issue) => issue.key)).toEqual(['text', 'answer', 'button', 'border', 'action']);
        expect(issues.find((issue) => issue.key === 'text')).toMatchObject({ minimum: AA_TEXT });
        expect(issues.find((issue) => issue.key === 'border')).toMatchObject({ minimum: AA_NON_TEXT });
        expect(issues.find((issue) => issue.key === 'text')!.ratio).toBeCloseTo(contrast('#9CA3AF', '#FFFFFF'), 5);
    });

    it.each(AWKWARD)('suggests colours that pass for %s', (_name, theme) => {
        const { fix } = themeContrastGuard(theme);
        expect(fix).not.toBeNull();
        expect(passesEverything({ ...theme, ...fix })).toBe(true);
    });

    it('moves only the colours that fail, keeping their hue', () => {
        const theme = { primary: '#101828', secondary: '#FDE68A', tertiary: '#818CA0', accent: '#FFFFFF' };
        const { fix } = themeContrastGuard(theme);
        expect(Object.keys(fix!)).toEqual(['secondary']);
        const [r, g, b] = hexChannels(fix!.secondary!)!;
        // still a yellow: red and green well above blue
        expect(r).toBeGreaterThan(b);
        expect(g).toBeGreaterThan(b);
        expect(contrast('#FFFFFF', fix!.secondary!)).toBeGreaterThanOrEqual(AA_TEXT);
    });

    it('turns a dark page pale, since answers sit in white boxes', () => {
        const theme = { primary: '#F9FAFB', secondary: '#60A5FA', tertiary: '#374151', accent: '#111827' };
        const { fix } = themeContrastGuard(theme);
        expect(contrast(fix!.accent!, '#FFFFFF')).toBeLessThan(1.5);
        expect(passesEverything({ ...theme, ...fix })).toBe(true);
    });

    it('checks text on both stops of a gradient', () => {
        const theme = { primary: '#101828', secondary: '#1649E2', tertiary: '#818CA0', accent: '#FFFFFF', background: { type: 'gradient' as const, gradientFrom: '#FFFFFF', gradientTo: '#101828' } };
        const { issues, fix } = themeContrastGuard(theme);
        expect(issues.map((issue) => issue.key)).toContain('text');
        expect(fix!.background).toMatchObject({ type: 'gradient', gradientFrom: '#FFFFFF' });
        expect(passesEverything({ ...theme, ...fix })).toBe(true);
    });

    it('cannot measure an image, but still checks the input boxes and buttons', () => {
        const image = { type: 'image' as const, imageUrl: '/api/v1/media/a.png' };
        expect(themeContrastGuard({ primary: '#FFFFFF', secondary: '#1649E2', tertiary: '#FFFFFF', accent: '#000000', background: image })).toMatchObject({ imageGround: true, issues: [{ key: 'answer' }] });
        expect(themeContrastGuard({ ...ThemeColors[0], background: image })).toEqual({ issues: [], fix: null, imageGround: true });
    });

    it('holds the margin sheet to the same rules as the page', () => {
        const theme = { primary: '#101828', secondary: '#1649E2', tertiary: '#F0F0F0', accent: '#1E4D3B', background: { type: 'pattern' as const, pattern: 'margin' as const } };
        expect(themeContrastGuard(theme).issues.map((issue) => issue.key)).toContain('border');
    });
});

describe('an outlined button', () => {
    const READABLE = { primary: '#101828', secondary: '#1649E2', tertiary: '#6B7280', accent: '#FFFFFF' };
    // White text on this orange is 3.3:1 (a filled button fails), and as text on white it is 3.3:1 too: an outlined button takes the dark ink instead.
    const MID_TONE = { ...READABLE, secondary: '#D9730D' };
    const outlined = { buttonStyle: 'outlined' as const };

    it('is its ink on the page, not white text on the button colour', () => {
        expect(themeContrastGuard(MID_TONE).issues.map((issue) => issue.key)).toEqual(['button']);
        expect(themeContrastGuard({ ...MID_TONE, ...outlined }).issues).toEqual([]);
        expect(themeContrastGuard({ ...MID_TONE, buttonStyle: 'pill' }).issues.map((issue) => issue.key)).toEqual(['button']);
    });

    it('takes the button colour as ink where it reads as text, else the questions colour', () => {
        expect(outlinedButtonInk({ ...READABLE, ...outlined })).toBe('#1649E2');
        expect(outlinedButtonInk({ ...MID_TONE, ...outlined })).toBe('#101828');
        expect(outlinedButtonInk({ ...READABLE, accent: '#0B1220', primary: '#F5F7FB', secondary: '#FFD166' })).toBe('#FFD166');
    });

    it('measures the real text and edge colours instead of skipping the check', () => {
        const pale = { primary: '#9CA3AF', secondary: '#F5C242', tertiary: '#E5E7EB', accent: '#FFFFFF', ...outlined };
        const issues = themeContrastGuard(pale).issues;
        expect(issues.map((issue) => issue.key)).not.toContain('button');
        const issue = issues.find((candidate) => candidate.key === 'outlined')!;
        // the ink falls back to the pale questions colour, which is 2.5:1 on the button's page-coloured ground
        expect(issue).toMatchObject({ minimum: AA_TEXT });
        expect(issue.ratio).toBeCloseTo(contrast('#9CA3AF', '#FFFFFF'), 5);
    });

    it('holds the edge to the page it sits against, a darker gradient stop included', () => {
        const theme = { ...READABLE, secondary: '#1E4D8C', ...outlined, background: { type: 'gradient' as const, gradientFrom: '#FFFFFF', gradientTo: '#7A8CB8' } };
        const [issue] = themeContrastGuard(theme).issues;
        expect(issue.key).toBe('outlined');
        expect(issue.ratio).toBeCloseTo(contrast('#1E4D8C', '#7A8CB8'), 5);
        expect(issue.minimum).toBe(AA_NON_TEXT);
    });

    it('needs a less dark button colour than a filled button, and the suggestion passes', () => {
        const yellow = { ...READABLE, secondary: '#F5C242' };
        const filled = themeContrastGuard(yellow).fix!;
        const fix = themeContrastGuard({ ...yellow, ...outlined }).fix!;
        expect(fix.secondary).not.toBe(filled.secondary);
        expect(contrast(fix.secondary!, '#FFFFFF')).toBeGreaterThanOrEqual(AA_NON_TEXT);
        expect(contrast(fix.secondary!, '#FFFFFF')).toBeLessThan(AA_TEXT);
        expect(themeContrastGuard({ ...yellow, ...fix, ...outlined }).issues).toEqual([]);
    });

    it('reads as the one theme for the presets, filled or outlined', () => {
        for (const preset of ThemeColors) {
            expect(themeContrastGuard({ ...preset, buttonStyle: 'outlined' }).issues, preset.title).toEqual([]);
            expect(themeContrastGuard({ ...preset, buttonStyle: 'filled' }).issues, preset.title).toEqual([]);
        }
    });

    it('replaces the white-on-button check of the themes checks with the ink on the page', () => {
        const keys = (theme: Parameters<typeof themeContrastChecks>[0]) => themeContrastChecks(theme).map((check) => check.key);
        expect(keys(READABLE)).toContain('button');
        expect(keys({ ...READABLE, ...outlined })).not.toContain('button');
        expect(keys({ ...READABLE, ...outlined })).toEqual(expect.arrayContaining(['outlined-text', 'outlined-edge']));
        for (const check of themeContrastChecks({ ...MID_TONE, ...outlined })) expect(check.ratio, check.label).toBeGreaterThanOrEqual(check.minimum);
    });
});

describe('contrastKey', () => {
    const theme = { primary: '#101828', secondary: '#1649E2', tertiary: '#6B7280', accent: '#FFFFFF' };

    it('ignores what the check does not read', () => {
        expect(contrastKey({ ...theme, title: 'x', titleFont: 'besley', radius: 'round', buttonStyle: 'pill' } as any)).toBe(contrastKey(theme as any));
        expect(contrastKey({ ...theme, primary: '#101828'.toLowerCase() } as any)).toBe(contrastKey(theme as any));
    });

    it('reads the colours, outlined buttons and what the background puts behind the text', () => {
        const base = contrastKey(theme as any);
        for (const change of [
            { primary: '#101829' },
            { secondary: '#1649E3' },
            { tertiary: '#6B7281' },
            { accent: '#FFFFFE' },
            { buttonStyle: 'outlined' },
            { background: { type: 'gradient', gradientFrom: '#FFFFFF' } },
            { background: { type: 'image', imageUrl: '/a.png' } }
        ]) {
            expect(contrastKey({ ...theme, ...change } as any), JSON.stringify(change)).not.toBe(base);
        }
    });
});
