import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key, i18n: { language: 'en' } }) }));
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast: vi.fn() }) }));
vi.mock('@app/store/jotai/workspace-settings-view', () => ({ useWorkspaceSettingsView: () => ({ settingsViewOpen: false, setSettingsViewOpen: vi.fn() }) }));
vi.mock('@app/components/dashboard/workspace-forms-tab-content', () => ({ default: () => <div /> }));
vi.mock('@app/components/dashboard/workspace-responses-tab-content', () => ({ default: () => <div /> }));
vi.mock('@Components/responder-portal/search-by-submission-number', () => ({ default: () => <div data-testid="search-card" /> }));
vi.mock('@Components/responder-portal/workspace-details-card', () => ({ default: () => <div data-testid="details-card" /> }));
vi.mock('@Components/workspace/workspace-settings-content', () => ({ default: () => <div /> }));
vi.mock('@app/utils/workspace-utils', () => ({ getWorkspaceShareURL: () => 'https://forms.example.test/acme' }));

import AppThemeScope from '@app/components/app-theme/app-theme-scope';
import { APP_ROLES_RESET_ON_FORMS } from '@app/lib/app-theme';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { colourAt } from '@app/test/app-theme-cascade';

import CreatorDashboardClient from './creator-dashboard-client';

// "Your site" is a preview of the public workspace page, which has no app theme scope and is blue: the preview wears the
// same colours, so the app roles are reset on its root as on a form's (formRootProps), and its tabs, its card and its
// search read the frozen blue in a Pigment workspace too. Outside a scope nothing is added.
const show = (scope: 'pigment' | 'daybreak' | null) => {
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme', title: 'Stichting Voorbeeld' } as any));
    const page = <CreatorDashboardClient hasCustomDomain={false} />;
    return render(<ReduxProvider store={store}>{scope ? <AppThemeScope workspaceId="ws-1" initial={scope}>{page}</AppThemeScope> : page}</ReduxProvider>);
};
const previewRoot = () => screen.getByTestId('search-card').parentElement!.parentElement as HTMLElement;

describe('the "Your site" preview', () => {
    it.each(['pigment', 'daybreak'] as const)('resets the app roles on its root inside a %s scope', (scope) => {
        show(scope);
        const root = previewRoot();
        for (const role of APP_ROLES_RESET_ON_FORMS) expect(root.style.getPropertyValue(role), role).toBe('initial');
    });

    it('carries the form-root marker, so rules that stay out of a form (the wash text colour, the native checkbox colour) stay out of the preview', () => {
        show('pigment');
        expect(previewRoot().hasAttribute('data-form-root')).toBe(true);
    });

    it('draws its tabs in the public page blue inside a Pigment scope, not in iris', () => {
        show('pigment');
        const tab = screen.getAllByRole('button').find((button) => button.className.includes('border-app-primary'))!;
        expect(tab).toBeTruthy();
        expect(colourAt(tab, '--color-app-primary')).toBe('#123FC9');
        // the same role outside the preview, in the same scope, is iris
        expect(colourAt(document.body.querySelector('[data-app-theme]')!, '--color-app-primary')).toBe('#4B35DB');
    });

    it('keeps the frame cream: `bg-canvas` is not a reset role, so the preview ground follows the theme', () => {
        show('pigment');
        expect(previewRoot().className).toContain('bg-canvas');
        expect(colourAt(previewRoot(), '--color-canvas')).toBe('#FBF7F1');
    });

    it('holds only the public-page preview: no creator control sits inside the reset root', () => {
        show('pigment');
        const root = previewRoot();
        // the copy-link button and the settings toggle are in the header above it
        expect(root.querySelector('[aria-pressed]')).toBeNull();
        expect(root.querySelector('a[href^="http"]')).toBeNull();
    });

    it('adds nothing when there is no scope', () => {
        show(null);
        expect(previewRoot().hasAttribute('data-form-root')).toBe(false);
        expect(previewRoot().getAttribute('style') ?? '').not.toContain('--app-');
    });
});
