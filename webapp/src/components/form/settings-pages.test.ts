// Which Settings pages a form has: a page that would be empty is not listed.
import { describe, expect, it } from 'vitest';

import { WorkspacePermission } from '@app/models/enums/workspace-permission';

import { isSettingsPageKey, settingsPages } from './settings-pages';

const can =
    (...granted: string[]) =>
    (permission: WorkspacePermission) =>
        granted.includes(permission);
const own = { builderVersion: 'v2', isPublished: true, settings: { provider: 'self' } } as any;
const imported = { builderVersion: 'v1', isPublished: true, importedFormId: 'g1', settings: { provider: 'google' } } as any;

describe('settingsPages', () => {
    it('gives a form made here all five pages', () => {
        expect(settingsPages(own, can(WorkspacePermission.FORM_EDIT))).toEqual(['access', 'availability', 'experience', 'automations', 'advanced']);
    });

    it('gives a published imported form Access, Respondent experience (branding) and Advanced (original form)', () => {
        expect(settingsPages(imported, can(WorkspacePermission.FORM_EDIT))).toEqual(['access', 'experience', 'advanced']);
    });

    it('leaves Respondent experience out of an unpublished imported form', () => {
        expect(settingsPages({ ...imported, isPublished: false }, can())).toEqual(['access', 'advanced']);
    });

    it('hides Advanced when nothing on it applies', () => {
        expect(settingsPages({ ...imported, importedFormId: undefined }, can())).toEqual(['access', 'experience']);
        expect(settingsPages({ ...own, builderVersion: 'v1' }, can())).toEqual(['access', 'availability', 'experience', 'automations']);
    });

    it('keeps Advanced for the delete button alone', () => {
        expect(settingsPages({ ...own, builderVersion: 'v1' }, can(WorkspacePermission.FORM_DELETE))).toContain('advanced');
    });

    it('knows its own names', () => {
        expect(['access', 'availability', 'experience', 'automations', 'advanced'].every(isSettingsPageKey)).toBe(true);
        expect(isSettingsPageKey('general')).toBe(false);
        expect(isSettingsPageKey(undefined)).toBe(false);
    });
});
