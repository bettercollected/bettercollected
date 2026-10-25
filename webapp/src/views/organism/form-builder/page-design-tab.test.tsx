// The builder's Design tab: the theme gallery applies a theme live, and the
// contrast guard flags a hard-to-read palette and fixes it in one click.
import React from 'react';

import { fireEvent, render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { ThemeColors, findPreset } from '@app/constants/theme';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { IFormState, useFormState } from '@app/store/jotai/form';
import { store } from '@app/store/store';
import { themeContrastProblems } from '@app/utils/publish-checks';

import PageDesignTab from './page-design-tab';

vi.mock('next/navigation', () => ({ usePathname: () => '/acme/dashboard/forms/f1/edit', useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), useSearchParams: () => new URLSearchParams() }));
vi.mock('@app/views/molecules/form-builder/form-logo-settings', () => ({ default: () => null }));

const pages: StandardFormFieldDto[] = [
    { id: 'p1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'a', index: 0, type: FieldTypes.MULTIPLE_CHOICE, title: 'Which day suits you?', properties: { choices: [{ id: 'c1', value: 'Monday' }] } } as StandardFormFieldDto] } }
];

let form: IFormState | null = null;

function Tab() {
    const builder = useFormFieldsAtom();
    form = useFormState().formState;
    const [ready, setReady] = React.useState(false);
    React.useEffect(() => {
        builder.initFormFields(pages);
        setReady(true);
    }, []);
    return ready ? <PageDesignTab /> : null;
}

const renderTab = () =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Tab />
            </Provider>
        </ReduxProvider>
    );

describe('the Design tab', () => {
    it('shows every preset as a thumbnail of this form, and applies the one picked', () => {
        renderTab();
        const gallery = screen.getByRole('radiogroup', { name: 'Theme' });
        expect(within(gallery).getAllByRole('radio')).toHaveLength(ThemeColors.length + 1);
        expect(within(gallery).getAllByText('Which day suits you?').length).toBe(ThemeColors.length + 1);
        fireEvent.click(within(gallery).getByRole('radio', { name: 'Raster' }));
        expect(form?.theme?.title).toBe('Raster');
        expect(form?.theme?.secondary).toBe(findPreset('Raster')!.secondary);
        expect(within(gallery).getByRole('radio', { name: 'Raster' })).toHaveAttribute('aria-checked', 'true');
    });

    it('guards a custom palette: flagged, blocked from publishing, fixed in one click', () => {
        renderTab();
        fireEvent.click(screen.getByRole('radio', { name: 'Custom colours' }));
        fireEvent.change(screen.getByLabelText('Questions & text'), { target: { value: '#c0c0c0' } });
        expect(screen.getByRole('radio', { name: 'Custom colours' })).toHaveAccessibleDescription('Hard to read');
        expect(screen.getByTestId('contrast-guard')).toHaveTextContent('Questions and text on the page');
        expect(themeContrastProblems(form?.theme)).toHaveLength(1);

        fireEvent.click(screen.getByRole('button', { name: 'Use the suggested colours' }));
        expect(form?.theme?.title).toBe('Custom');
        expect(themeContrastProblems(form?.theme)).toEqual([]);
        expect(screen.getByTestId('contrast-guard')).toHaveTextContent('Readable');
    });
});
