import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { afterEach, describe, expect, it, vi } from 'vitest';

import I18nProvider from '@app/shared/hocs/i18n-provider';

import TrustLayer, { TrustLayerProps } from './trust-layer';

function setBrowserLanguages(languages: string[]) {
    vi.spyOn(window.navigator, 'languages', 'get').mockReturnValue(languages);
}

// A fresh jotai store per render: the respondent's language choice is per visit.
const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <Provider>
        <I18nProvider>{children}</I18nProvider>
    </Provider>
);

const renderPanel = (props: TrustLayerProps) => render(<TrustLayer {...props} />, { wrapper: Wrapper });

const openPanel = () => fireEvent.click(screen.getByRole('button', { expanded: false }));

const row = (key: string) => screen.getByTestId(`privacy-${key}`);

describe('Privacy panel on respondent forms', () => {
    afterEach(() => {
        vi.restoreAllMocks();
        window.history.replaceState(null, '', '/');
    });

    it('is a real disclosure: collapsed strip with a button that opens and closes the panel', () => {
        setBrowserLanguages(['en-GB']);
        renderPanel({ ownerName: 'Acme Health' });
        expect(screen.getByText(/Collected by/)).toBeInTheDocument();
        expect(screen.queryByRole('region')).not.toBeInTheDocument();

        const toggle = screen.getByRole('button', { name: /your privacy/i });
        expect(toggle).toHaveAttribute('aria-expanded', 'false');
        fireEvent.click(toggle);
        expect(toggle).toHaveAttribute('aria-expanded', 'true');
        const panel = screen.getByRole('region', { name: /your privacy/i });
        expect(toggle).toHaveAttribute('aria-controls', panel.id);

        // Escape closes it and hands focus back to the button.
        fireEvent.keyDown(panel, { key: 'Escape' });
        expect(toggle).toHaveAttribute('aria-expanded', 'false');
        expect(toggle).toHaveFocus();
    });

    it('opens by default when asked (the welcome page) until the respondent closes it', () => {
        setBrowserLanguages(['en']);
        const { rerender } = render(<TrustLayer ownerName="Acme" defaultExpanded />, { wrapper: Wrapper });
        expect(screen.getByRole('region')).toBeInTheDocument();
        rerender(<TrustLayer ownerName="Acme" defaultExpanded={false} />);
        expect(screen.queryByRole('region')).not.toBeInTheDocument();
    });

    it('states who, why, how long, identity and rights in English', () => {
        setBrowserLanguages(['en-US']);
        renderPanel({
            ownerName: 'Acme Health',
            portalUrl: 'https://forms.test/acme',
            settings: { purpose: 'To book your appointment', requireVerifiedIdentity: true, responseExpirationType: 'days', responseExpiration: '90' }
        });
        openPanel();
        expect(row('receiver')).toHaveTextContent('Who receives your answersAcme Health');
        expect(row('purpose')).toHaveTextContent('To book your appointment');
        expect(row('retention')).toHaveTextContent('Kept for 90 days after you submit.');
        expect(row('identity')).toHaveTextContent('You verify your email address before you can answer.');
        expect(row('rights')).toHaveTextContent('You can view your answers and ask for them to be deleted at any time.');
        expect(within(row('rights')).getByRole('link', { name: /view or delete your response/i })).toHaveAttribute('href', 'https://forms.test/acme');
    });

    it('speaks Dutch to a Dutch browser', () => {
        setBrowserLanguages(['nl-NL', 'en']);
        renderPanel({ ownerName: 'Gemeente Voorbeeld', settings: { purpose: 'Om uw afspraak te plannen', responseExpirationType: 'days', responseExpiration: '1' } });
        expect(screen.getByText(/Verzameld door/)).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: /je privacy/i }));
        expect(screen.getByRole('heading', { name: 'Wat er met je antwoorden gebeurt' })).toBeInTheDocument();
        expect(row('receiver')).toHaveTextContent('Wie je antwoorden ontvangt');
        expect(row('retention')).toHaveTextContent('Bewaard tot 1 dag na het insturen.');
        expect(row('identity')).toHaveTextContent('Bevestigen is niet nodig. Je kunt antwoorden zonder in te loggen.');
        expect(row('rights')).toHaveTextContent('Je kunt je antwoorden altijd inzien en laten verwijderen.');
    });

    it('lets the share link and the respondent choose the language', () => {
        setBrowserLanguages(['en']);
        window.history.replaceState(null, '', '/?lang=nl');
        renderPanel({ ownerName: 'Acme' });
        openPanel();
        expect(screen.getByRole('heading', { name: 'Wat er met je antwoorden gebeurt' })).toBeInTheDocument();

        act(() => fireEvent.click(screen.getByRole('button', { name: 'English' })));
        expect(screen.getByRole('heading', { name: 'How your answers are handled' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'English' })).toHaveAttribute('aria-pressed', 'true');
    });

    it('mentions AI only when the form opted in to AI insights', () => {
        setBrowserLanguages(['en']);
        const { unmount } = renderPanel({ ownerName: 'Acme', settings: { aiInsightsEnabled: true, aiInsightsProviderName: 'OpenAI' } });
        openPanel();
        expect(row('ai')).toHaveTextContent('Your answers are processed by AI (OpenAI) to help analyse the responses.');
        unmount();

        renderPanel({ ownerName: 'Acme', settings: { aiInsightsEnabled: false, aiInsightsProviderName: 'OpenAI' } });
        openPanel();
        expect(screen.queryByTestId('privacy-ai')).not.toBeInTheDocument();
        expect(screen.queryByText(/AI/)).not.toBeInTheDocument();
    });

    it('states AI use in Dutch too', () => {
        setBrowserLanguages(['nl']);
        renderPanel({ ownerName: 'Acme', settings: { aiInsightsEnabled: true, aiInsightsProviderName: 'Mistral' } });
        openPanel();
        expect(row('ai')).toHaveTextContent('Je antwoorden worden door AI (Mistral) verwerkt om de reacties te helpen analyseren.');
    });

    it('never invents a retention period', () => {
        setBrowserLanguages(['en']);
        const { unmount } = renderPanel({ ownerName: 'Acme', settings: { responseExpirationType: 'days', responseExpiration: 'soon' } });
        openPanel();
        expect(row('retention')).toHaveTextContent('No fixed period: kept until they are deleted.');
        unmount();

        setBrowserLanguages(['nl']);
        renderPanel({ ownerName: 'Acme', settings: {} });
        openPanel();
        expect(row('retention')).toHaveTextContent('Geen vaste termijn: bewaard tot ze worden verwijderd.');
    });

    it("prefers the creator's own retention wording, and states a date period in the respondent's language", () => {
        setBrowserLanguages(['nl']);
        const { unmount } = renderPanel({ ownerName: 'Acme', settings: { responseExpirationType: 'date', responseExpiration: '2027-03-01' } });
        openPanel();
        expect(row('retention')).toHaveTextContent('Bewaard tot 1 maart 2027.');
        unmount();

        renderPanel({ ownerName: 'Acme', settings: { retentionText: 'Tot het einde van het project', responseExpirationType: 'days', responseExpiration: '30' } });
        openPanel();
        expect(row('retention')).toHaveTextContent('Tot het einde van het project');
    });

    it('links the privacy policy only when there is one, and keeps attribution behind the branding setting', () => {
        setBrowserLanguages(['en']);
        const { unmount } = renderPanel({ ownerName: 'Acme', settings: { privacyPolicyUrl: 'https://acme.test/privacy', disableBranding: false } });
        openPanel();
        expect(screen.getByRole('link', { name: /privacy policy/i })).toHaveAttribute('href', 'https://acme.test/privacy');
        expect(screen.getByRole('link', { name: /powered by/i })).toHaveAttribute('href', 'https://bettercollected.com/');
        unmount();

        renderPanel({ ownerName: 'Acme', settings: { disableBranding: true } });
        openPanel();
        expect(screen.queryByRole('link', { name: /privacy policy/i })).not.toBeInTheDocument();
        expect(screen.queryByText(/powered by/i)).not.toBeInTheDocument();
    });
});
