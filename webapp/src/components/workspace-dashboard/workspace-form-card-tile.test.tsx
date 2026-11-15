// A form's tile on its card: the same size and the same visibility on a phone whether it is the form's own
// picture or its coloured initial, and not on the responder portal's card.
import React from 'react';

import { cleanup, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';

import WorkspaceFormCard from './workspace-form-card';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn() }) }));
vi.mock('@app/lib/hooks/use-group-form', () => ({ useGroupForm: () => ({ deleteFormFromGroup: vi.fn() }) }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: () => false, ready: true, isLoading: false }) }));
vi.mock('@Components/datatable/form-options-dropdown', () => ({ default: () => null }));

const workspace = { id: 'ws1', workspaceName: 'acme' } as any;
const form = (change: Record<string, unknown> = {}) => ({ formId: 'f1', title: 'Survey', isPublished: true, builderVersion: 'v2', settings: { provider: 'self' }, ...change }) as any;

const renderCard = (value: any, portal = false) =>
    render(
        <ReduxProvider store={store}>
            <WorkspaceFormCard form={value} workspace={workspace} hasCustomDomain={false} isResponderPortal={portal} />
        </ReduxProvider>
    );

afterEach(cleanup);

describe('the tile on a form card', () => {
    it('is the coloured initial, shown at every width and sized for a phone first', () => {
        renderCard(form());
        const tile = screen.getByTestId('form-avatar');
        expect(tile).toHaveTextContent('S');
        expect(tile.className).toContain('h-9 w-9');
        expect(tile.className).not.toMatch(/(^| )hidden( |$)/);
    });

    it('is the same size and as visible when the form has a logo or a cover instead', () => {
        const { container } = renderCard(form({ logo: 'https://images.example/logo.png' }));
        const image = container.querySelector('img')!;
        expect(screen.queryByTestId('form-avatar')).toBeNull();
        expect(image.className).toContain('h-9 w-9');
        expect(image.className).toContain('sm:h-11 sm:w-11');
        expect(image.className).not.toMatch(/(^| )hidden( |$)/);
    });

    it('is not on the responder portal card', () => {
        renderCard(form(), true);
        expect(screen.queryByTestId('form-avatar')).toBeNull();
    });
});
