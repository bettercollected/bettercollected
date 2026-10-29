// "Last edited 4 hours ago" on a form card is in one language: the label from
// the locale files and the time from the same language.
import React from 'react';

import { render, screen } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';

import WorkspaceFormCard from './workspace-form-card';

import commonNl from '../../../public/locales/nl/common.json';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn() }) }));
vi.mock('@app/lib/hooks/use-group-form', () => ({ useGroupForm: () => ({ deleteFormFromGroup: vi.fn() }) }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: () => false, ready: true, isLoading: false }) }));
vi.mock('@Components/datatable/form-options-dropdown', () => ({ default: () => null }));

const workspace = { id: 'ws1', workspaceName: 'acme' } as any;
const fourHoursAgo = () => new Date(Date.now() - 4 * 3600 * 1000 - 60 * 1000).toISOString();
const draft = () => ({ formId: 'f1', title: 'Klantfeedback', isPublished: false, builderVersion: 'v2', updatedAt: fourHoursAgo(), settings: { provider: 'self' } }) as any;

const renderCard = (form: any) =>
    render(
        <ReduxProvider store={store}>
            <WorkspaceFormCard form={form} workspace={workspace} hasCustomDomain={false} />
        </ReduxProvider>
    );

beforeAll(() => {
    i18n.addResourceBundle('nl', 'common', commonNl, true, true);
});

afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('the last-edited time on a form card', () => {
    it('is Dutch in Dutch', async () => {
        await i18n.changeLanguage('nl');
        renderCard(draft());
        expect(screen.getByText('Laatst bewerkt 4 uur geleden')).toBeInTheDocument();
        expect(screen.queryByText(/ago/)).toBeNull();
    });

    it('is Dutch on a published card too', async () => {
        await i18n.changeLanguage('nl');
        renderCard({ ...draft(), isPublished: true });
        expect(screen.getByText('Laatst bewerkt 4 uur geleden')).toBeInTheDocument();
    });

    it('is English in English', () => {
        renderCard(draft());
        expect(screen.getByText('Last edited 4 hours ago')).toBeInTheDocument();
    });
});
