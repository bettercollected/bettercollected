import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { FormSlideLayout } from '@app/models/enums/form';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';

import WelcomePage from './welcome-page';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));

const renderWith = (layout: FormSlideLayout) => {
    store.dispatch(setForm({ formId: `welcome-${layout}`, title: 'Visit feedback', fields: [], welcomePage: { description: 'Three minutes.', layout } }));
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <WelcomePage isPreviewMode />
            </Provider>
        </ReduxProvider>
    );
};

describe('WelcomePage layout', () => {
    it('"Centered" centres the title, description, note and button', () => {
        renderWith(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND);
        const column = screen.getByTestId('welcome-column');
        expect(column.className).toContain('text-center');
        expect(column.className).toContain('items-center');
        expect(column.className).toContain('mx-auto');
        expect(screen.getByRole('heading', { level: 1, name: 'Visit feedback' })).toBeDefined();
        expect(screen.getByRole('button', { name: 'Start' })).toBeDefined();
    });

    it('"Left aligned" keeps one left edge', () => {
        renderWith(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN);
        const column = screen.getByTestId('welcome-column');
        expect(column.className).not.toContain('text-center');
        expect(column.className).toContain('items-start');
        expect(column.className).toContain('mr-auto');
    });
});
