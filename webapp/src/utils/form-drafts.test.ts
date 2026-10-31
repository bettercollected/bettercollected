import { afterEach, describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';

import { DEFAULT_DRAFT_DAYS, answersForDraft, draftDays, draftErrorKey, draftsOffered, forgetResumeToken, hasFileQuestion, positionForDraft, restoreDraft, resumeTokenOf, takeResumeToken } from './form-drafts';

const q = (id: string, type: FieldTypes, extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({ id, index: 0, type, title: id, properties: { fields: [] }, ...extra });
const page = (id: string, fields: StandardFormFieldDto[]): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SLIDE, title: '', properties: { fields } });

const FORM = {
    hiddenFields: ['source'],
    fields: [
        page('p1', [q('name', FieldTypes.SHORT_TEXT), q('cv', FieldTypes.FILE_UPLOAD), q('total', FieldTypes.CALCULATED)]),
        page('p2', [q('colour', FieldTypes.MULTIPLE_CHOICE), q('kids', FieldTypes.GROUP, { properties: { fields: [q('kid', FieldTypes.SHORT_TEXT)], repeat: { minItems: 0, maxItems: 3 } } as any }), q('office', FieldTypes.SHORT_TEXT, { internal: true })]),
        page('p3', [q('later', FieldTypes.SHORT_TEXT)])
    ]
};
const text = (value: string) => ({ type: 'text', text: value });

describe('draftDays', () => {
    it('is the setting when it is 1 to 90 days, else 30', () => {
        expect(draftDays({ draftRetentionDays: 14 } as any)).toBe(14);
        expect(draftDays({ draftRetentionDays: 90 } as any)).toBe(90);
        for (const days of [0, 91, -1, 2.5, null, undefined, '7' as any]) expect(draftDays({ draftRetentionDays: days } as any)).toBe(DEFAULT_DRAFT_DAYS);
        expect(draftDays(undefined)).toBe(30);
    });
});

describe('draftsOffered', () => {
    it('needs the setting, and a sign-in when the form asks for a verified identity', () => {
        expect(draftsOffered(undefined, true)).toBe(false);
        expect(draftsOffered({ allowSaveDraft: false } as any, true)).toBe(false);
        expect(draftsOffered({ allowSaveDraft: true } as any, false)).toBe(true);
        expect(draftsOffered({ allowSaveDraft: true, requireVerifiedIdentity: true } as any, false)).toBe(false);
        expect(draftsOffered({ allowSaveDraft: true, requireVerifiedIdentity: true } as any, true)).toBe(true);
    });
});

describe('what a draft keeps', () => {
    it('drops files, calculations, internal and unknown answers, and keeps the rest', () => {
        const kept = answersForDraft(FORM.fields, { name: text('Ada'), cv: { type: 'file_upload' }, total: { type: 'number', number: 3 }, ghost: text('x'), office: text('staff'), colour: { type: 'choice', choice: { value: 'c1' } } });
        expect(Object.keys(kept).sort()).toEqual(['colour', 'name']);
    });

    it('keeps the items of a repeating group, without answers to unknown questions', () => {
        const kept = answersForDraft(FORM.fields, { kids: { type: 'group', items: [{ kid: text('Bo'), gone: text('x') }, { kid: text('Cy') }] } });
        expect(kept.kids.items).toEqual([{ kid: text('Bo') }, { kid: text('Cy') }]);
    });

    it('knows whether the form asks for a file', () => {
        expect(hasFileQuestion(FORM.fields)).toBe(true);
        expect(hasFileQuestion([page('p', [q('a', FieldTypes.SHORT_TEXT)])])).toBe(false);
    });
});

describe('position', () => {
    it('is stored by page id, without the welcome page', () => {
        expect(positionForDraft(FORM.fields, 2, [-1, 0, 1])).toEqual({ pageId: 'p3', history: ['p1', 'p2'] });
        expect(positionForDraft(FORM.fields, 0, [-1])).toEqual({ pageId: 'p1', history: [] });
    });

    it('is found again in a changed form', () => {
        const draft = { answers: {}, hiddenFields: {}, position: { pageId: 'p3', history: ['p1', 'p2'] } };
        expect(restoreDraft(FORM, draft)).toMatchObject({ slide: 2, history: [-1, 0, 1] });
        // the page was removed: start at the first one
        const without = { ...FORM, fields: [FORM.fields[0], FORM.fields[1]] };
        expect(restoreDraft(without, draft)).toMatchObject({ slide: 0, history: [-1] });
    });
});

describe('restoring a draft', () => {
    it('counts the answers the form has no question for and ignores undeclared names', () => {
        const restored = restoreDraft(FORM, { answers: { name: text('Ada'), ghost: text('x'), kids: { type: 'group', items: [{ kid: text('Bo'), gone: text('y') }] } }, hiddenFields: { source: 'news', other: 'x' }, position: null });
        expect(Object.keys(restored.answers).sort()).toEqual(['kids', 'name']);
        expect(restored.dropped).toBe(2);
        expect(restored.hiddenFields).toEqual({ source: 'news' });
        expect(restored).toMatchObject({ slide: 0, history: [-1] });
    });
});

describe('the link', () => {
    it('is read only in its exact shape', () => {
        const token = `${'a'.repeat(24)}.${'B'.repeat(43)}`;
        expect(resumeTokenOf(`#resume=${token}`)).toBe(token);
        for (const bad of ['', '#', '#resume=', '#resume=short', `#resume=${token}&x=1`, `#x=1;resume=${token}`, `resume=${token}`, `#resume=${token}x`]) expect(resumeTokenOf(bad)).toBeNull();
    });
});

describe('errors', () => {
    it.each([
        [{ status: 429 }, 'DRAFT.ERR_RATE'],
        [{ status: 413 }, 'DRAFT.ERR_TOO_LARGE'],
        [{ status: 403, data: { code: 'sign_in_required' } }, 'DRAFT.ERR_SIGN_IN'],
        [{ status: 503, data: { code: 'link_not_sent' } }, 'DRAFT.ERR_LINK_NOT_SENT'],
        [{ status: 422, data: { code: 'invalid_email' } }, 'DRAFT.ERR_EMAIL'],
        [{ status: 409, data: { code: 'form_closed' } }, 'DRAFT.ERR_CLOSED'],
        [{ status: 409, data: { code: 'drafts_off' } }, 'DRAFT.ERR_OFF'],
        [{ status: 409, data: { code: 'draft_limit' } }, 'DRAFT.ERR_LIMIT'],
        [{ status: 404, data: { code: 'drafts_off' } }, 'DRAFT.ERR_OFF'],
        [{ status: 404, data: { code: 'draft_not_found' } }, 'DRAFT.ERR_NOT_FOUND'],
        [{ status: 500 }, 'DRAFT.ERR_FAILED'],
        [undefined, 'DRAFT.ERR_FAILED']
    ])('%j is %s', (error, key) => expect(draftErrorKey(error)).toBe(key));
});

describe('taking the link from the address bar', () => {
    const TOKEN = `${'a'.repeat(24)}.${'B'.repeat(43)}`;
    afterEach(() => {
        forgetResumeToken();
        window.history.replaceState(null, '', '/');
    });

    it('returns the token and removes the fragment from the address bar at once', () => {
        window.history.replaceState(null, '', `/acme/forms/f1?lang=nl#resume=${TOKEN}`);
        expect(takeResumeToken()).toBe(TOKEN);
        expect(window.location.hash).toBe('');
        expect(window.location.pathname + window.location.search).toBe('/acme/forms/f1?lang=nl');
        expect(window.location.href).not.toContain(TOKEN);
    });

    it('hands the token out again to a development double render, and not for long', () => {
        window.history.replaceState(null, '', `/acme/forms/f1#resume=${TOKEN}`);
        const at = 1_000_000;
        expect(takeResumeToken(at)).toBe(TOKEN);
        expect(takeResumeToken(at + 10)).toBe(TOKEN);
        expect(takeResumeToken(at + 5000)).toBeNull();
    });

    it('takes nothing from an address without a link, or with one that is not in its exact shape', () => {
        window.history.replaceState(null, '', `/acme/forms/f1#resume=${TOKEN}x`);
        expect(takeResumeToken()).toBeNull();
        // left as it is: it is not ours
        expect(window.location.hash).toBe(`#resume=${TOKEN}x`);
        window.history.replaceState(null, '', '/acme/forms/f1');
        expect(takeResumeToken()).toBeNull();
    });
});
