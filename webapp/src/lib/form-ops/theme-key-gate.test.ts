import { describe, expect, it } from 'vitest';

import { GATED_THEME_KEYS, offeredThemeKeys, unofferedThemeKeyProblem } from '@app/constants/theme';

import { applyOps } from '@app/lib/form-ops';

/**
 * The `choiceKeys` theme key follows the one Pigment switch, as the backend's
 * `_check_theme_offered` does (backend/tests/app/controllers/test_choice_keys_gate.py):
 * a new theme that sets it while the switch is off is refused, unless the stored
 * theme at the same place already has it. The shared corpus (`pigmentPreset`)
 * holds the cases both engines must agree on.
 */

const COLOURS = { title: 'Mine', primary: '#1A1238', secondary: '#4B35DB', tertiary: '#7C7396', accent: '#FBF7F1' };
const KEYED = { ...COLOURS, choiceKeys: 'letters' };
const REFUSED = 'choiceKeys is not available yet.';

const page = (theme?: unknown) => ({ id: 'p1', index: 0, type: 'slide', properties: { fields: [{ id: 'q1', index: 0, type: 'short_text', title: 'Name' }], ...(theme ? { theme } : {}) } });
const doc = (theme?: unknown, pageTheme?: unknown) => ({ title: 'F', builderVersion: 'v2', ...(theme ? { theme } : {}), fields: [page(pageTheme)] }) as any;

describe('the gated theme keys', () => {
    it('are the choice keys, on the Pigment switch (the backend list)', () => {
        expect(GATED_THEME_KEYS).toEqual({ choiceKeys: 'app_theme.ENABLED' });
        expect(offeredThemeKeys(true)).toEqual(['choiceKeys']);
        expect(offeredThemeKeys(false)).toEqual([]);
    });

    it('are refused word for word as the backend does, or kept where the stored theme has them', () => {
        expect(unofferedThemeKeyProblem(KEYED, null, 'theme', [])).toBe(`theme.${REFUSED}`);
        expect(unofferedThemeKeyProblem(KEYED, null, 'fields.0.properties.theme', [])).toBe(`fields.0.properties.theme.${REFUSED}`);
        expect(unofferedThemeKeyProblem(KEYED, null, 'theme', ['choiceKeys'])).toBeNull();
        // not asked while the server's list is not known
        expect(unofferedThemeKeyProblem(KEYED, null, 'theme', undefined)).toBeNull();
        // a theme without the key is as it was
        expect(unofferedThemeKeyProblem(COLOURS, null, 'theme', [])).toBeNull();
        expect(unofferedThemeKeyProblem({ ...COLOURS, choiceKeys: null }, null, 'theme', [])).toBeNull();
        // the stored theme at that place has it
        expect(unofferedThemeKeyProblem(KEYED, { choiceKeys: 'letters' }, 'theme', [])).toBeNull();
        expect(unofferedThemeKeyProblem(KEYED, { title: 'Other' }, 'theme', [])).toBe(`theme.${REFUSED}`);
    });
});

describe('the edit engine', () => {
    it('update_theme refuses a new key while the switch is off and keeps a stored one', () => {
        const off = applyOps(doc(COLOURS), [{ op: 'update_theme', theme: KEYED }] as any, { offeredThemeKeys: [] });
        expect(off.results[0].ok).toBe(false);
        expect(off.results[0].message).toBe(`theme.${REFUSED}`);
        const kept = applyOps(doc(KEYED), [{ op: 'update_theme', theme: { ...KEYED, title: 'Renamed' } }] as any, { offeredThemeKeys: [] });
        expect(kept.results[0].ok).toBe(true);
        expect((kept.doc as any).theme.choiceKeys).toBe('letters');
        const plain = applyOps(doc(KEYED), [{ op: 'update_theme', theme: COLOURS }] as any, { offeredThemeKeys: [] });
        expect(plain.results[0].ok).toBe(true);
        const on = applyOps(doc(COLOURS), [{ op: 'update_theme', theme: KEYED }] as any, { offeredThemeKeys: ['choiceKeys'] });
        expect(on.results[0].ok).toBe(true);
        // no list (the server's answer not known): nothing is checked
        expect(applyOps(doc(COLOURS), [{ op: 'update_theme', theme: KEYED }] as any).results[0].ok).toBe(true);
    });

    it('update_page refuses a new key on a page theme while the switch is off and keeps a stored one', () => {
        const patch = [{ op: 'update_page', pageId: 'p1', patch: { theme: KEYED } }] as any;
        const off = applyOps(doc(COLOURS), patch, { offeredThemeKeys: [] });
        expect(off.results[0].ok).toBe(false);
        expect(off.results[0].message).toBe(`theme.${REFUSED}`);
        const kept = applyOps(doc(COLOURS, KEYED), patch, { offeredThemeKeys: [] });
        expect(kept.results[0].ok).toBe(true);
        expect(applyOps(doc(COLOURS), patch, { offeredThemeKeys: ['choiceKeys'] }).results[0].ok).toBe(true);
    });
});
