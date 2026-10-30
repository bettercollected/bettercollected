import i18n from 'i18next';
import { afterEach, describe, expect, it } from 'vitest';

import '@app/shared/hocs/i18n-provider';

import { droppedRulesNotice } from './audo-save-form';

describe('the notice for field rules a save left out', () => {
    afterEach(async () => {
        await i18n.changeLanguage('en');
    });

    it('says nothing when the server dropped nothing', () => {
        expect(droppedRulesNotice({ title: 'x' })).toBeNull();
        expect(droppedRulesNotice({ droppedFieldRules: [] })).toBeNull();
        expect(droppedRulesNotice(undefined)).toBeNull();
    });

    it('counts questions, not rules, in English and Dutch', async () => {
        await i18n.changeLanguage('en');
        const one = [
            { fieldId: 'b', ruleId: 'r1', message: 'x' },
            { fieldId: 'b', ruleId: 'r2', message: 'y' }
        ];
        expect(droppedRulesNotice({ droppedFieldRules: one })).toContain('1 question could not be kept');
        const two = [...one, { fieldId: 'c', ruleId: 'r3', message: 'z' }];
        expect(droppedRulesNotice({ droppedFieldRules: two })).toContain('2 questions could not be kept');
        await i18n.changeLanguage('nl');
        expect(droppedRulesNotice({ droppedFieldRules: two })).toContain('2 vragen konden niet blijven staan');
    });
});
