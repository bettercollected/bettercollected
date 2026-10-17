import { describe, expect, it } from 'vitest';

import { formStateFromServerForm, initialFormState, IFormState } from './form';

const current: IFormState = {
    ...initialFormState,
    title: 'Old title',
    description: 'Old description',
    hiddenFields: ['ref'],
    logoPosition: 'left',
    logoAlt: 'Old logo',
    useWorkspaceLogo: true
};

describe('formStateFromServerForm', () => {
    it('copies every form-level part of the server form', () => {
        const theme = { title: 'Ocean', primary: '#111827', secondary: '#1D4ED8', tertiary: '#2563EB', accent: '#DBEAFE', background: { type: 'gradient' as const, gradientFrom: '#000000', gradientTo: '#FFFFFF' } };
        const server = {
            title: 'New title',
            description: 'New description',
            theme,
            welcomePage: { title: 'New title', description: 'Hello' },
            thankyouPage: [{ title: 'Thanks' }],
            hiddenFields: ['utm_source'],
            logoPosition: 'center',
            logoAlt: 'New logo',
            useWorkspaceLogo: false,
            fields: [{ id: 'page-1' }]
        };
        const next = formStateFromServerForm(current, server);
        expect(next.title).toBe('New title');
        expect(next.description).toBe('New description');
        expect(next.theme).toEqual(theme);
        expect(next.theme).not.toBe(theme);
        expect(next.theme?.background).not.toBe(theme.background);
        expect(next.welcomePage).toEqual({ title: 'New title', description: 'Hello' });
        expect(next.thankyouPage).toEqual([{ title: 'Thanks' }]);
        expect(next.hiddenFields).toEqual(['utm_source']);
        expect(next.logoPosition).toBe('center');
        expect(next.logoAlt).toBe('New logo');
        expect(next.useWorkspaceLogo).toBe(false);
        // Fields live in their own atom (with undo history), not here.
        expect((next as any).fields).toBeUndefined();
    });

    it('keeps what the server form leaves out', () => {
        const next = formStateFromServerForm(current, { title: 'Only the title', theme: null });
        expect(next.title).toBe('Only the title');
        expect(next.description).toBe('Old description');
        expect(next.theme).toBe(current.theme);
        expect(next.welcomePage).toBe(current.welcomePage);
        expect(next.hiddenFields).toEqual(['ref']);
        expect(next.useWorkspaceLogo).toBe(true);
    });

    it('a cleared description stays cleared', () => {
        expect(formStateFromServerForm(current, { description: null }).description).toBeNull();
    });

    it('no form changes nothing', () => {
        expect(formStateFromServerForm(current, undefined)).toBe(current);
    });
});
