import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';

import ReviewPageSetting from './review-page-setting';

const patch = vi.fn();
vi.mock('@app/store/workspaces/api', async (original) => ({
    ...((await original()) as object),
    usePatchFormSettingsMutation: () => [(args: unknown) => ({ then: (resolve: any) => resolve(patch(args)) }), {}]
}));
const toast = vi.fn();
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast }) }));

const open = (settings: Record<string, unknown> = {}) => {
    store.dispatch(setForm({ formId: 'f1', title: 'Survey', settings, fields: [] } as any));
    store.dispatch(setWorkspace({ id: 'w1', workspaceName: 'acme' } as any));
    return render(
        <ReduxProvider store={store}>
            <ReviewPageSetting />
        </ReduxProvider>
    );
};
const switchControl = () => screen.getByRole('switch', { name: /review answers before sending|antwoorden laten controleren/i });

beforeEach(() => {
    patch.mockReset();
    toast.mockReset();
});
afterEach(async () => {
    await act(() => i18n.changeLanguage('en'));
});

describe('the "review answers before sending" setting', () => {
    it('is off by default and says what it does', () => {
        open();
        expect(switchControl()).not.toBeChecked();
        expect(switchControl()).toHaveAccessibleDescription(/Nothing is sent or stored until they do/);
    });

    it('shows a form that has it on', () => {
        open({ showReviewPage: true });
        expect(switchControl()).toBeChecked();
    });

    it('saves the switch through the settings request, and the form follows the answer', async () => {
        patch.mockReturnValue({ data: { settings: { showReviewPage: true, purpose: 'To plan.' } } });
        open({ purpose: 'To plan.' });
        await act(async () => void fireEvent.click(switchControl()));
        expect(patch).toHaveBeenCalledWith({ workspaceId: 'w1', formId: 'f1', body: { showReviewPage: true } });
        await waitFor(() => expect(switchControl()).toBeChecked());
        expect(store.getState().form.settings).toMatchObject({ showReviewPage: true, purpose: 'To plan.' });
    });

    it('says when it could not be saved, and stays as it was', async () => {
        patch.mockReturnValue({ error: { status: 500 } });
        open();
        await act(async () => void fireEvent.click(switchControl()));
        expect(toast).toHaveBeenCalledWith({ description: 'The setting could not be saved. Please try again.', variant: 'destructive' });
        expect(switchControl()).not.toBeChecked();
    });

    it.each([
        ['en', 'Before sending', 'Review answers before sending'],
        ['nl', 'Voor het verzenden', 'Antwoorden laten controleren voor het verzenden']
    ])('is written in %s and passes axe', async (language, title, label) => {
        await act(() => i18n.changeLanguage(language));
        open();
        expect(screen.getByRole('heading', { name: title })).toBeInTheDocument();
        expect(screen.getByLabelText(label)).toBeInTheDocument();
        expect(await axeViolations(document.body)).toEqual([]);
    });
});
