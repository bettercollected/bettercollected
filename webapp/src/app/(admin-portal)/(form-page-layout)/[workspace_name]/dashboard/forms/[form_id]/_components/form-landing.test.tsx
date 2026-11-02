// Where a form opens: Responses for a published form whose responses the person may read, else Pages.
import React from 'react';

import { render } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';

import FormLanding, { landingSection } from './form-landing';

const replace = vi.hoisted(() => vi.fn());
const perms = vi.hoisted(() => ({ granted: [] as string[], ready: true }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace }) }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: (permission: string) => perms.granted.includes(permission), ready: perms.ready }) }));

const BASE = '/acme/dashboard/forms/f1';
const land = (form: Record<string, unknown> | null) => {
    store.dispatch(setForm(form ? ({ formId: 'f1', builderVersion: 'v2', isPublished: true, settings: { provider: 'self' }, ...form } as any) : ({} as any)));
    return render(
        <ReduxProvider store={store}>
            <FormLanding base={BASE} />
        </ReduxProvider>
    );
};

describe('where a form opens', () => {
    beforeEach(() => {
        replace.mockClear();
        perms.granted = ['response.read', 'form.edit'];
        perms.ready = true;
    });

    it('is Responses for a published form, for who may read its responses', () => {
        land({});
        expect(replace).toHaveBeenCalledWith(`${BASE}/responses`);
        expect(replace).toHaveBeenCalledTimes(1);
    });

    it('is Pages for a draft, which has no responses', () => {
        land({ isPublished: false });
        expect(replace).toHaveBeenCalledWith(`${BASE}/preview`);
    });

    it('is Pages for who may not read responses', () => {
        perms.granted = ['form.edit'];
        land({});
        expect(replace).toHaveBeenCalledWith(`${BASE}/preview`);
    });

    it('is Responses for a published form imported from elsewhere too (its Pages have nothing to show)', () => {
        land({ builderVersion: undefined, settings: { provider: 'google' } });
        expect(replace).toHaveBeenCalledWith(`${BASE}/responses`);
    });

    it('waits for the permissions: a guess now could send somebody to a page they cannot open', () => {
        perms.ready = false;
        land({});
        expect(replace).not.toHaveBeenCalled();
    });

    it('waits for the form', () => {
        land(null);
        expect(replace).not.toHaveBeenCalled();
    });

    it('shows nothing itself', () => {
        expect(land({}).container).toBeEmptyDOMElement();
    });
});

describe('landingSection', () => {
    it('needs both a published form and response.read', () => {
        expect(landingSection({ isPublished: true }, true)).toBe('responses');
        expect(landingSection({ isPublished: true }, false)).toBe('preview');
        expect(landingSection({ isPublished: false }, true)).toBe('preview');
        expect(landingSection(undefined, true)).toBe('preview');
    });
});
