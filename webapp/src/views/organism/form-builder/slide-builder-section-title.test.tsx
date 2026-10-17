import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { store } from '@app/store/store';

import SlideBuilder from './slide-builder';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/dashboard/forms/f1/edit',
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
    useSearchParams: () => new URLSearchParams()
}));
// The rich-text editor and the field renderers are not what is tested here.
vi.mock('@app/views/molecules/rich-text-editor', () => ({
    RichTextEditor: ({ field }: { field: StandardFormFieldDto }) => <div data-testid={`editor-${field.id}`} />
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ default: () => null }));
vi.mock('@app/views/molecules/form-builder/plain-language-hints', () => ({ default: () => null }));
vi.mock('@app/lib/hooks/use-form-logo', () => ({ useBuilderFormLogo: () => null }));

const LEAFLET = { title: 'Leaflet', primary: '#1A1A1A', secondary: '#0B3D91', tertiary: '#6B7A99', accent: '#FFFFFF', style: 'leaflet' as const };
const question = (id: string, title: string): StandardFormFieldDto => ({ id, index: 1, type: FieldTypes.SHORT_TEXT, title });
const opening = (content: any[]): StandardFormFieldDto => ({ id: 'intro', index: 0, type: FieldTypes.TEXT, title: { type: 'doc', content } as any });
const heading = { type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: 'About your visit' }] };

let fields: ReturnType<typeof useFormFieldsAtom> | null = null;

function Canvas({ page }: { page: StandardFormFieldDto }) {
    const atom = useFormFieldsAtom();
    const { updateFormTheme } = useFormState();
    fields = atom;
    React.useEffect(() => {
        updateFormTheme(LEAFLET);
        atom.initFormFields([page]);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    const slide = atom.formFields[0];
    if (!slide || slide.id !== page.id) return null;
    return <SlideBuilder slide={slide} />;
}

const renderPage = (page: StandardFormFieldDto) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Canvas page={page} />
            </Provider>
        </ReduxProvider>
    );

const page = (pageFields: StandardFormFieldDto[], sectionTitle?: string): StandardFormFieldDto => ({ id: 'page-1', index: 0, type: FieldTypes.SLIDE, properties: { fields: pageFields, ...(sectionTitle !== undefined ? { sectionTitle } : {}) } });

describe('section title on the Leaflet bar in the builder', () => {
    it('is edited inline on the bar; empty, the placeholder shows the fallback', async () => {
        renderPage(page([question('q', 'What is your name?')]));
        const bar = await screen.findByTestId('leaflet-section-bar');
        const input = within(bar).getByRole('textbox', { name: 'Section title' }) as HTMLTextAreaElement;
        expect(input.value).toBe('');
        expect(input.placeholder).toBe('What is your name?');
        expect(input.maxLength).toBe(120);
        // It sits in the bar's heading, after the numeral.
        expect(within(bar).getByRole('heading', { level: 2 })).toContainElement(input);

        act(() => {
            fireEvent.change(input, { target: { value: 'About you' } });
        });
        expect(fields!.formFields[0].properties?.sectionTitle).toBe('About you');
        expect((screen.getByRole('textbox', { name: 'Section title' }) as HTMLTextAreaElement).value).toBe('About you');

        // Line breaks are not part of a title.
        act(() => {
            fireEvent.change(input, { target: { value: 'About\nyou' } });
        });
        expect(fields!.formFields[0].properties?.sectionTitle).toBe('About you');

        // Clearing returns the bar to its fallback.
        act(() => {
            fireEvent.change(input, { target: { value: '' } });
        });
        expect(fields!.formFields[0].properties?.sectionTitle).toBe('');
        expect((screen.getByRole('textbox', { name: 'Section title' }) as HTMLTextAreaElement).placeholder).toBe('What is your name?');
    });

    it('with an opening heading and no title, the heading is the bar; with a title, the heading stays in the band', async () => {
        const { unmount } = renderPage(page([opening([heading]), question('q', 'Name')]));
        await screen.findByTestId('editor-intro');
        // The heading is edited in place on the bar (the opening block's editor): no separate bar.
        expect(screen.queryByTestId('leaflet-section-bar')).toBeNull();
        unmount();

        renderPage(page([opening([heading]), question('q', 'Name')], 'Your visit'));
        const bar = await screen.findByTestId('leaflet-section-bar');
        const input = within(bar).getByRole('textbox', { name: 'Section title' }) as HTMLTextAreaElement;
        expect(input.value).toBe('Your visit');
        expect(input.placeholder).toBe('About your visit');
        // The opening block (heading included) is edited in the band below the bar.
        expect(screen.getByTestId('leaflet-canvas-opening')).toContainElement(screen.getByTestId('editor-intro'));
    });
});
