import { existsSync, readFileSync } from 'fs';
import { resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { ThemeColors, findPreset } from '@app/constants/theme';

// The backend's copy of the presets (forms the AI, the API and imports dress).
// This list is the source of truth; the backend's own test compares colours
// and styles, this one keeps the names together from the webapp side.
const BACKEND_THEMES = resolve(__dirname, '../../../backend/backend/app/constants/themes.py');

describe('findPreset', () => {
    it.each(ThemeColors.map((preset) => [preset.title]))('finds %s by its title', (title) => {
        expect(findPreset(title)?.title).toBe(title);
    });

    it('matches a title in any case, as the AI may send it', () => {
        expect(findPreset(' ocean ')?.title).toBe('Ocean');
        expect(findPreset('LEAFLET')?.style).toBe('leaflet');
    });

    it('finds nothing for a custom, a missing or a legacy title', () => {
        expect(findPreset('Custom')).toBeUndefined();
        expect(findPreset(undefined)).toBeUndefined();
        expect(findPreset('')).toBeUndefined();
        // legacy backend names were mapped to presets server-side; a form that
        // still stores one keeps its own colours and shows as no preset
        expect(findPreset('Blue')).toBeUndefined();
    });
});

describe('backend presets', () => {
    it('carry the same names, in the same order', () => {
        if (!existsSync(BACKEND_THEMES)) return; // webapp checked out on its own
        const source = readFileSync(BACKEND_THEMES, 'utf-8');
        const block = source.slice(source.indexOf('theme_dict = {'), source.indexOf('LEGACY_PRESET_NAMES = {'));
        const titles = Array.from(block.matchAll(/"title": "(\w+)"/g), (match) => match[1]);
        expect(titles).toEqual(ThemeColors.map((preset) => preset.title));
    });
});
