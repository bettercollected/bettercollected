import { describe, expect, it } from 'vitest';

import { defaultForm } from '@app/constants/form';
import { NEW_FORM_THEME_TITLE, ThemeColors, newFormTheme } from '@app/constants/theme';
import { initialFormState } from '@app/store/jotai/form';

describe('the theme new forms start with', () => {
    it('is the Leaflet preset, in the Leaflet style', () => {
        expect(NEW_FORM_THEME_TITLE).toBe('Leaflet');
        expect(newFormTheme()).toEqual({ title: 'Leaflet', primary: '#1A1A1A', secondary: '#0B3D91', tertiary: '#6B7A99', accent: '#FFFFFF', style: 'leaflet' });
    });

    it('is what a blank form (and a draft for the AI assistant) is created with', () => {
        expect(defaultForm.theme).toEqual(newFormTheme());
    });

    it('is a copy: changing one form never changes the preset', () => {
        const theme = newFormTheme();
        theme.primary = '#000000';
        expect(ThemeColors.find((preset) => preset.title === 'Leaflet')?.primary).toBe('#1A1A1A');
    });

    it('leaves stored forms alone: a form without a theme still renders as Default', () => {
        expect(initialFormState.theme?.title).toBe('Default');
        expect(ThemeColors[0].title).toBe('Default');
    });
});
