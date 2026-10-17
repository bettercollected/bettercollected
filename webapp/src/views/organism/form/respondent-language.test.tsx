// Respondent text resolves through the app's i18n instance.
import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';

import FormSlide from './form-slide';
import ThankyouPage from './thankyou-page';
import WelcomePage, { startButtonText } from './welcome-page';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));
// RenderImage drags in the whole builder field registry — irrelevant here.
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const question = (id: string, type: FieldTypes, required = false): StandardFormFieldDto => ({ id, index: 0, type, title: `Question ${id}`, validations: { required } });
const slide = (id: string, index: number, fields: StandardFormFieldDto[]): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, properties: { fields } });

const threePages = (welcomeButton?: string) =>
    store.dispatch(
        setForm({
            formId: 'lang-form',
            title: 'Bezoek',
            welcomePage: { buttonText: welcomeButton },
            fields: [slide('s1', 0, [question('q1', FieldTypes.SHORT_TEXT), question('q2', FieldTypes.YES_NO, true)]), slide('s2', 1, []), slide('s3', 2, [])]
        })
    );

const wrap = (node: React.ReactNode) =>
    render(
        <ReduxProvider store={store}>
            <Provider>{node}</Provider>
        </ReduxProvider>
    );

/** Open the form as a share link with `?lang=`. */
const withLang = (lang: string) => window.history.replaceState(null, '', `/acme/forms/f1?lang=${lang}`);

describe('respondent text follows the respondent language', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
    });
    afterEach(() => window.history.replaceState(null, '', '/'));

    it('header, markers and button in Dutch with ?lang=nl', async () => {
        withLang('nl');
        threePages();
        wrap(<FormSlide index={0} isPreviewMode />);

        // Back's visible text and accessible name stay the same.
        expect(await screen.findByRole('button', { name: 'Vorige' })).toHaveTextContent('Vorige');
        expect(screen.getByText('Pagina 1 van 3')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Volgende' })).toBeInTheDocument();
        expect(screen.getByText('Niet verplicht')).toBeInTheDocument();
        expect(screen.getByText('(verplicht)')).toBeInTheDocument();
        expect(screen.getByText('Ja')).toBeInTheDocument();
        expect(screen.getByText('Nee')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('Antwoord')).toBeInTheDocument();
    });

    it('stays English with ?lang=en', async () => {
        withLang('en');
        threePages();
        wrap(<FormSlide index={0} isPreviewMode />);

        expect(await screen.findByRole('button', { name: 'Back' })).toBeInTheDocument();
        expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument();
        expect(screen.getByText('Optional')).toBeInTheDocument();
        expect(screen.getByText('Yes')).toBeInTheDocument();
    });

    it("welcome page: Dutch default start button, the creator's own text untouched", async () => {
        withLang('nl');
        threePages();
        const { unmount } = wrap(<WelcomePage isPreviewMode />);
        expect(await screen.findByRole('button', { name: 'Beginnen' })).toBeInTheDocument();
        expect(screen.getByText('Bevestig je e-mailadres.')).toBeInTheDocument();
        unmount();

        threePages('Aan de slag');
        wrap(<WelcomePage isPreviewMode />);
        expect(await screen.findByRole('button', { name: 'Aan de slag' })).toBeInTheDocument();
    });

    it('ending page: the default title and message in Dutch', async () => {
        withLang('nl');
        store.dispatch(setForm({ formId: 'lang-ending', title: 'Bezoek', thankyouPage: null, fields: [] }));
        wrap(<ThankyouPage isPreviewMode />);
        expect(await screen.findByText('Bedankt')).toBeInTheDocument();
        expect(screen.getByText('Je antwoorden zijn verstuurd.')).toBeInTheDocument();
    });
});

describe('startButtonText', () => {
    it('translates only the default', () => {
        expect(startButtonText(undefined, 'Beginnen')).toBe('Beginnen');
        expect(startButtonText('  ', 'Beginnen')).toBe('Beginnen');
        expect(startButtonText('Start', 'Beginnen')).toBe('Beginnen');
        expect(startButtonText('Begin the survey', 'Beginnen')).toBe('Begin the survey');
    });
});
