// Author text carries the form's language (`lang`) when it differs from the
// respondent's interface language, and nothing when the two are the same.
import React from 'react';

import { cleanup, render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useFormState } from '@app/store/jotai/form';
import { store } from '@app/store/store';
import InputField from '@app/views/molecules/responder-form-fields/input-field';
import RepeatingGroupField from '@app/views/molecules/responder-form-fields/repeating-group-field';
import ImageField from '@app/views/organism/form-builder/fields/image-field';

import FormSlide from './form-slide';
import WelcomePage from './welcome-page';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));

const LEAFLET = { title: 'Leaflet', primary: '#1A1A1A', secondary: '#0B3D91', tertiary: '#6B7A99', accent: '#FFFFFF', style: 'leaflet' as const };
const short = (id: string, title: string): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SHORT_TEXT, title });
const slide = (id: string, index: number, fields: StandardFormFieldDto[], sectionTitle?: string): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, properties: { fields, sectionTitle } as any });

const group: StandardFormFieldDto = {
    id: 'g',
    index: 0,
    type: FieldTypes.GROUP,
    title: 'Applicants',
    properties: { repeat: { minItems: 1, maxItems: 2, itemLabel: 'Aanvrager' }, fields: [short('name', 'Name')] } as any
};
const imageField: StandardFormFieldDto = { id: 'img', index: 0, type: FieldTypes.IMAGE_CONTENT, title: 'Photo', attachment: { href: '/media/photo.png', properties: { description: 'Het gebouw van voren' } } } as any;

const loadForm = (language: string | undefined, extra: Record<string, any> = {}) =>
    store.dispatch(
        setForm({
            formId: `marking-${language}-${Math.random()}`,
            title: 'Bezoekersonderzoek',
            theme: LEAFLET,
            welcomePage: { description: 'Drie korte pagina’s.', buttonText: 'Begin' },
            settings: { language },
            fields: [slide('s1', 0, [short('a', 'Uw naam')], 'Uw gegevens'), slide('s2', 1, [short('b', 'Uw bezoek')], 'Over uw bezoek'), slide('s3', 2, [short('c', 'Uw stad')])],
            ...extra
        } as any)
    );

const Themed = ({ children }: { children: React.ReactNode }) => {
    const { updateFormTheme } = useFormState();
    React.useEffect(() => {
        updateFormTheme((store.getState() as any).form.theme);
    }, []);
    return <>{children}</>;
};

const wrap = (node: React.ReactNode) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Themed>{node}</Themed>
            </Provider>
        </ReduxProvider>
    );

/** The `lang` that applies to `node`: its own or the nearest ancestor's (below the page root). */
const langOf = (node: HTMLElement) => node.closest('[lang]')?.getAttribute('lang') ?? null;

const visit = (search: string) => window.history.replaceState(null, '', `/acme/forms/f1${search}`);

// [form language, page language, expected lang on author text]
const CASES: Array<[string, string, string | null]> = [
    ['nl', 'en', 'nl'],
    ['en-GB', 'nl', 'en-GB'],
    ['nl', 'nl', null],
    ['en-GB', 'en', null]
];

describe.each(CASES)('author text of a %s form on a %s page', (formLanguage, pageLanguage, expected) => {
    beforeEach(() => visit(`?lang=${pageLanguage}`));
    afterEach(() => {
        cleanup();
        window.history.replaceState(null, '', '/');
    });

    it('marks the Leaflet section bar heading', () => {
        loadForm(formLanguage);
        wrap(<FormSlide index={1} isPreviewMode />);
        const bar = screen.getByTestId('leaflet-section-bar');
        expect(langOf(within(bar).getByText('Over uw bezoek'))).toBe(expected);
    });

    it('marks the welcome page\'s "In this form" list, but not the page\'s own fallback', () => {
        loadForm(formLanguage);
        wrap(<WelcomePage isPreviewMode />);
        const items = within(screen.getByTestId('leaflet-contents')).getAllByRole('listitem');
        expect(langOf(within(items[0]).getByText('Uw gegevens'))).toBe(expected);
        // The third page has no title of its own: its first question names it, so it is the form's text too.
        expect(langOf(within(items[2]).getByText('Uw stad'))).toBe(expected);
    });

    it("marks the start button's creator wording, not the default", () => {
        loadForm(formLanguage);
        wrap(<WelcomePage isPreviewMode />);
        expect(langOf(screen.getByText('Begin'))).toBe(expected);
        cleanup();

        loadForm(formLanguage, { welcomePage: { description: 'Kort.' } });
        wrap(<WelcomePage isPreviewMode />);
        const start = screen.getByRole('button', { name: pageLanguage === 'nl' ? 'Beginnen' : 'Start' });
        expect(start.closest('[lang]')?.getAttribute('lang') ?? null).not.toBe(formLanguage);
    });

    it("marks a repeating group's item heading when the creator named the item", () => {
        loadForm(formLanguage);
        wrap(<RepeatingGroupField field={group} renderChild={(child) => <InputField field={child} />} />);
        expect(langOf(screen.getByRole('heading', { name: 'Aanvrager 1' }))).toBe(expected);
    });

    it("marks a picture's description", () => {
        loadForm(formLanguage);
        wrap(<ImageField field={imageField} />);
        expect(langOf(screen.getByAltText('Het gebouw van voren'))).toBe(expected);
    });
});

describe('what stays unmarked', () => {
    beforeEach(() => visit('?lang=en'));
    afterEach(() => {
        cleanup();
        window.history.replaceState(null, '', '/');
    });

    it("a repeating group's default item name is the page's, not the form's", () => {
        loadForm('nl');
        const unnamed = { ...group, properties: { ...group.properties, repeat: { minItems: 1, maxItems: 2 } } } as StandardFormFieldDto;
        wrap(<RepeatingGroupField field={unnamed} renderChild={(child) => <InputField field={child} />} />);
        expect(langOf(screen.getByRole('heading', { name: 'Item 1' }))).toBeNull();
    });

    it('a picture without a description is decorative and carries no language', () => {
        loadForm('nl');
        const plain = { ...imageField, attachment: { href: '/media/photo.png', properties: {} } } as StandardFormFieldDto;
        wrap(<ImageField field={plain} />);
        expect(document.querySelector('img')?.getAttribute('lang') ?? null).toBeNull();
    });

    it('a form that declares no language marks nothing', () => {
        loadForm(undefined);
        wrap(<WelcomePage isPreviewMode />);
        expect(langOf(screen.getByText('Begin'))).toBeNull();
        expect(langOf(screen.getByText('Uw gegevens'))).toBeNull();
    });
});
