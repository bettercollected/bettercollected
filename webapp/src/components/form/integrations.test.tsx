// A form's integrations (Settings): each added action has a named on/off
// switch and a named "more" menu.
import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { axeViolations } from '@app/test/axe';

import FormIntegrations from './integrations';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));
vi.mock('@app/store/api-actions-api', async (importOriginal) => ({
    ...(await importOriginal<typeof import('@app/store/api-actions-api')>()),
    useGetAllIntegrationsQuery: () => ({
        data: [
            { id: 'a-sheets', title: 'Google Sheets', description: 'Add each submission as a row.', url: '/integration/default.svg' },
            { id: 'a-hook', title: 'Webhook', description: 'Post each submission to a URL.', url: '/integration/default.svg' }
        ]
    }),
    useRemoveActionFromFormMutation: () => [vi.fn()],
    useUpdateActionStatusInFormMutation: () => [vi.fn()]
}));

describe('form integrations', () => {
    it("names an added action's switch and menu after the action", async () => {
        store.dispatch(setForm({ formId: 'f1', title: 'Job application', actions: { on_submit: [{ id: 'a-sheets', enabled: true }] } } as any));
        const { container } = render(
            <ReduxProvider store={store}>
                <FormIntegrations />
            </ReduxProvider>
        );

        expect(screen.getByRole('switch', { name: 'Turn Google Sheets on or off' })).toBeChecked();
        expect(screen.getByRole('button', { name: 'More actions for Google Sheets' })).toHaveAttribute('aria-haspopup', 'menu');
        // the action not added yet has neither
        expect(screen.queryByRole('switch', { name: /Webhook/ })).toBeNull();
        expect(await axeViolations(container)).toEqual([]);
    });
});
