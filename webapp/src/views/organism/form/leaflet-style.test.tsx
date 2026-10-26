// Respondent text resolves through the app's i18n instance.
import React from 'react';

import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Comparison, LogicalOperator } from '@app/models/types/form-builder-shared';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useFormState } from '@app/store/jotai/form';
import { store } from '@app/store/store';

import FormSlide from './form-slide';
import ThankyouPage from './thankyou-page';
import WelcomePage from './welcome-page';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const LEAFLET = { title: 'Leaflet', primary: '#1A1A1A', secondary: '#0B3D91', tertiary: '#6B7A99', accent: '#FFFFFF', style: 'leaflet' as const };
const question = (id: string, type: FieldTypes, extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({ id, index: 0, type, title: `Question ${id}`, ...extra });
const intro = (id: string, content: any[]): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.TEXT, title: { type: 'doc', content } as any });
const slide = (id: string, index: number, fields: StandardFormFieldDto[]): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, properties: { fields } });
const showWhenYes = { action: 'SHOW', operator: LogicalOperator.AND, conditions: [{ fieldId: 'contact', fieldType: FieldTypes.YES_NO, comparison: Comparison.IS_EQUAL, value: 'Yes' }] };

const leafletForm = () =>
    store.dispatch(
        setForm({
            formId: 'leaflet-form',
            title: 'Open day feedback',
            theme: LEAFLET,
            welcomePage: { description: 'Three short pages.' },
            settings: { responseExpirationType: 'days', responseExpiration: '30' } as any,
            fields: [
                slide('s1', 0, [intro('t1', [{ type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: 'Your details' }] }]), question('name', FieldTypes.SHORT_TEXT, { validations: { required: true } })]),
                slide('s2', 1, [
                    intro('t2', [
                        { type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: 'About your visit' }] },
                        { type: 'paragraph', content: [{ type: 'text', text: 'Tell us how it went.' }] }
                    ]),
                    question('contact', FieldTypes.YES_NO),
                    question('phone', FieldTypes.PHONE_NUMBER, { properties: { logic: showWhenYes as any, whyWeAsk: 'Only to call you back.' } }),
                    question('comments', FieldTypes.LONG_TEXT)
                ]),
                slide('s3', 2, [intro('t3', [{ type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: 'Booking' }] }]), question('city', FieldTypes.SHORT_TEXT)])
            ]
        } as any)
    );

// The respondent page puts the form's theme in both stores (redux for the
// page, jotai for the fields); do the same here.
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

const numbers = () => screen.queryAllByTestId('question-number').map((n) => n.textContent);

describe('Leaflet style', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        leafletForm();
    });

    it('a page is a numbered section: bar with numeral and the opening heading, intro band, n.m questions', async () => {
        wrap(<FormSlide index={1} isPreviewMode />);
        const bar = await screen.findByTestId('leaflet-section-bar');
        expect(within(bar).getByRole('heading', { level: 2 }).textContent).toBe('2About your visit');
        expect(within(bar).getByTestId('leaflet-section-numeral').textContent).toBe('2');
        expect(within(screen.getByTestId('leaflet-intro-band')).getByText('Tell us how it went.')).toBeInTheDocument();
        // The heading moved to the bar: it is not repeated in the page.
        expect(screen.getAllByText('About your visit')).toHaveLength(1);
        // The phone question is hidden by logic until "Yes": numbers stay contiguous.
        expect(numbers()).toEqual(['2.1', '2.2']);
    });

    it('a question revealed by logic takes its place in the numbering', async () => {
        wrap(<FormSlide index={1} isPreviewMode />);
        act(() => {
            fireEvent.click(screen.getByRole('radio', { name: 'Yes' }));
        });
        expect(numbers()).toEqual(['2.1', '2.2', '2.3']);
        // Its reason reads as a margin note.
        expect(screen.getByText('Only to call you back.').closest('p')?.className).toContain('border-l-[3px]');
    });

    it('marks required questions in signal red', async () => {
        wrap(<FormSlide index={0} isPreviewMode />);
        const marker = (await screen.findByText('(required)')).previousSibling as HTMLElement;
        expect(marker.style.color).toBe('rgb(200, 16, 46)');
    });

    it('the welcome page is the leaflet cover, with the contents of the form', async () => {
        wrap(<WelcomePage isPreviewMode />);
        expect(await screen.findByRole('heading', { level: 1, name: 'Open day feedback' })).toBeInTheDocument();
        const contents = screen.getByTestId('leaflet-contents');
        expect(
            within(contents)
                .getAllByRole('listitem')
                .map((item) => item.textContent)
        ).toEqual(['1Your details', '2About your visit', '3Booking']);
        expect(screen.getByRole('button', { name: 'Start' })).toBeInTheDocument();
    });

    it('the ending says what happens next', async () => {
        wrap(<ThankyouPage isPreviewMode />);
        const next = await screen.findByTestId('leaflet-next');
        expect(within(next).getByRole('heading', { name: 'What happens next' })).toBeInTheDocument();
        // The period alone after its label, not "Kept for ...".
        expect(within(next).getAllByRole('listitem')[0].textContent).toBe('How long they are kept: 30 days after you submit.');
        expect(within(next).getByText(/You can view your answers/)).toBeInTheDocument();
        // Every row names its subject.
        expect(
            within(next)
                .getAllByRole('listitem')
                .map((row) => row.querySelector('span.font-semibold')?.textContent)
        ).toEqual(['How long they are kept:', 'Your rights:']);
        // The plain default title.
        expect(screen.getByRole('heading', { level: 1, name: 'Thank you' })).toBeInTheDocument();
    });

    it('the contents list a page without a heading under its first question, like its bar', async () => {
        const form = (store.getState() as any).form;
        store.dispatch(setForm({ ...form, fields: [form.fields[0], { ...form.fields[1], properties: { fields: [question('q', FieldTypes.SHORT_TEXT)] } }, form.fields[2]] } as any));
        wrap(<WelcomePage isPreviewMode />);
        const contents = await screen.findByTestId('leaflet-contents');
        expect(
            within(contents)
                .getAllByRole('listitem')
                .map((item) => item.textContent)
        ).toEqual(['1Your details', '2Question q', '3Booking']);
    });

    it('in Dutch, the ending row reads the period alone after its label', async () => {
        window.history.replaceState(null, '', '/acme/forms/f1?lang=nl');
        store.dispatch(setForm({ ...(store.getState() as any).form, settings: { responseExpirationType: 'days', responseExpiration: '1' } } as any));
        wrap(<ThankyouPage isPreviewMode />);
        const next = await screen.findByTestId('leaflet-next');
        await waitFor(() => expect(within(next).getAllByRole('listitem')[0].textContent).toBe('Hoe lang ze bewaard worden: 1 dag na het insturen.'));
        window.history.replaceState(null, '', '/');
    });

    it("the ending states one period: the creator's own wording is not added beside it", async () => {
        store.dispatch(setForm({ ...(store.getState() as any).form, settings: { retentionText: 'kept for 6 months' } } as any));
        wrap(<ThankyouPage isPreviewMode />);
        const next = await screen.findByTestId('leaflet-next');
        expect(within(next).getAllByRole('listitem')[0].textContent).toBe('How long they are kept: No fixed period. They are kept until they are deleted.');
        expect(next).not.toHaveTextContent(/6 months/);
    });

    it('a section title of its own goes on the bar and in the contents; the heading stays in the band', async () => {
        const form = (store.getState() as any).form;
        const titled = { ...form.fields[1], properties: { ...form.fields[1].properties, sectionTitle: '  Your  visit ' } };
        store.dispatch(setForm({ ...form, fields: [form.fields[0], titled, form.fields[2]] } as any));
        wrap(<FormSlide index={1} isPreviewMode />);
        const bar = await screen.findByTestId('leaflet-section-bar');
        expect(within(bar).getByRole('heading', { level: 2 }).textContent).toBe('2Your visit');
        const band = screen.getByTestId('leaflet-intro-band');
        expect(within(band).getByText('About your visit')).toBeInTheDocument();
        expect(within(band).getByText('Tell us how it went.')).toBeInTheDocument();
    });

    it('the contents list shows a page under its section title', async () => {
        const form = (store.getState() as any).form;
        const titled = { ...form.fields[2], properties: { ...form.fields[2].properties, sectionTitle: 'Choose a time' } };
        const cleared = { ...form.fields[1], properties: { ...form.fields[1].properties, sectionTitle: '   ' } };
        store.dispatch(setForm({ ...form, fields: [form.fields[0], cleared, titled] } as any));
        wrap(<WelcomePage isPreviewMode />);
        const contents = await screen.findByTestId('leaflet-contents');
        expect(
            within(contents)
                .getAllByRole('listitem')
                .map((item) => item.textContent)
        ).toEqual(['1Your details', '2About your visit', '3Choose a time']);
    });

    it('a page without a heading names its bar after its first question', async () => {
        const form = (store.getState() as any).form;
        store.dispatch(setForm({ ...form, fields: [{ ...form.fields[0], properties: { fields: [question('name', FieldTypes.SHORT_TEXT)] } }, form.fields[1], form.fields[2]] } as any));
        wrap(<FormSlide index={0} isPreviewMode />);
        const bar = await screen.findByTestId('leaflet-section-bar');
        expect(within(bar).getByRole('heading', { level: 2 }).textContent).toBe('1Question name');
        expect(within(bar).queryByText('Open day feedback')).toBeNull();
    });

    it('a question with an error marks its control invalid, describes it by the message and gives it the red edge', async () => {
        wrap(<FormSlide index={0} isPreviewMode />);
        act(() => {
            fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
        });
        const message = await screen.findByText('Please answer this question to continue.');
        const input = screen.getByPlaceholderText('Answer');
        expect(input.getAttribute('aria-invalid')).toBe('true');
        expect(input.getAttribute('aria-describedby')).toContain(message.closest('[role=alert]')!.id);
        const group = input.closest('[data-question-wrapper]') as HTMLElement;
        expect(group.style.getPropertyValue('--invalid-edge')).toBe('#C8102E');
    });

    it("section titles are marked with the form's language; the page's own fallback is not", async () => {
        const form = (store.getState() as any).form;
        store.dispatch(setForm({ ...form, settings: { ...form.settings, language: 'nl' }, fields: [...form.fields, slide('s4', 3, [])] }));

        wrap(<FormSlide index={1} isPreviewMode />);
        const bar = await screen.findByTestId('leaflet-section-bar');
        expect(within(bar).getByText('About your visit').closest('[lang]')).toHaveAttribute('lang', 'nl');
        cleanup();

        wrap(<WelcomePage isPreviewMode />);
        const contents = await screen.findByTestId('leaflet-contents');
        const items = within(contents).getAllByRole('listitem');
        expect(within(items[0]).getByText('Your details').closest('[lang]')).toHaveAttribute('lang', 'nl');
        // "Section 4": the page's language, not the form's
        expect(within(items[3]).getByText('Section 4').closest('[lang]')).toBeNull();
    });

    it('other styles carry no section bar and no numbers', async () => {
        store.dispatch(setForm({ ...(store.getState() as any).form, theme: { ...LEAFLET, style: 'classic' } } as any));
        wrap(<FormSlide index={1} isPreviewMode />);
        await screen.findByRole('radiogroup');
        expect(screen.queryByTestId('leaflet-section-bar')).toBeNull();
        expect(numbers()).toEqual([]);
    });
});
