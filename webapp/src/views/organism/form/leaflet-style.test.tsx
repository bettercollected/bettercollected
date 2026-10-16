// Respondent text resolves through the app's i18n instance.
import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
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
        expect(within(next).getByText(/Kept for 30 days after you submit/)).toBeInTheDocument();
        expect(within(next).getByText(/You can view your answers/)).toBeInTheDocument();
    });

    it('other styles carry no section bar and no numbers', async () => {
        store.dispatch(setForm({ ...(store.getState() as any).form, theme: { ...LEAFLET, style: 'classic' } } as any));
        wrap(<FormSlide index={1} isPreviewMode />);
        await screen.findByRole('radiogroup');
        expect(screen.queryByTestId('leaflet-section-bar')).toBeNull();
        expect(numbers()).toEqual([]);
    });
});
