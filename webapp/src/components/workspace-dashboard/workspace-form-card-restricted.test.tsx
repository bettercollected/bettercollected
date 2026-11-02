import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';

import WorkspaceFormCard from './workspace-form-card';

const served = vi.hoisted(() => ({ enabled: true }));

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn() }) }));
vi.mock('@app/lib/hooks/use-group-form', () => ({ useGroupForm: () => ({ deleteFormFromGroup: vi.fn() }) }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: () => false, ready: true, isLoading: false, formAccessEnabled: served.enabled }) }));
vi.mock('@Components/datatable/form-options-dropdown', () => ({ default: () => null }));

const workspace = { id: 'ws1', workspaceName: 'acme' } as any;
const form = (access?: Record<string, unknown>) => ({ formId: 'f1', title: 'Join the volunteers', isPublished: true, builderVersion: 'v2', settings: { provider: 'self' }, ...(access ? { access } : {}) }) as any;

const renderCard = (props: Record<string, unknown> = {}, access?: Record<string, unknown>) =>
    render(
        <ReduxProvider store={store}>
            <WorkspaceFormCard form={form(access)} workspace={workspace} hasCustomDomain={false} {...props} />
        </ReduxProvider>
    );

describe('a form card in the dashboard list', () => {
    beforeEach(() => {
        served.enabled = true;
    });

    it('says Restricted, in words, for a restricted form while form-level access is on', () => {
        renderCard({}, { restricted: true });
        expect(screen.getByTestId('restricted-chip').textContent).toBe('Restricted');
    });

    it('has no chip for an open form, one the payload does not describe, or while the switch is off', () => {
        const open = renderCard({}, { restricted: false });
        expect(screen.queryByTestId('restricted-chip')).toBeNull();
        open.unmount();
        const bare = renderCard();
        expect(screen.queryByTestId('restricted-chip')).toBeNull();
        bare.unmount();
        served.enabled = false;
        renderCard({}, { restricted: true });
        expect(screen.queryByTestId('restricted-chip')).toBeNull();
    });

    it('never shows it to respondents', () => {
        renderCard({ isResponderPortal: true }, { restricted: true });
        expect(screen.queryByTestId('restricted-chip')).toBeNull();
    });
});
