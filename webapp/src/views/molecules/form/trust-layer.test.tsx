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
        expect(row('identity')).toHaveTextContent('You sign in with your email address before you can answer.');
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
        expect(row('retention')).toHaveTextContent('Bewaard gedurende 1 dag na het insturen.');
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
        expect(row('ai')).toHaveTextContent("Your answers may be analysed by AI (OpenAI) when the form's team runs AI insights.");
        unmount();

        renderPanel({ ownerName: 'Acme', settings: { aiInsightsEnabled: false, aiInsightsProviderName: 'OpenAI' } });
        openPanel();
        expect(screen.queryByTestId('privacy-ai')).not.toBeInTheDocument();
        expect(screen.queryByText(/AI/)).not.toBeInTheDocument();
    });

    it('states AI use in the always-visible strip, without opening the panel (#752)', () => {
        setBrowserLanguages(['en']);
        const { unmount } = renderPanel({ ownerName: 'Acme', settings: { aiInsightsEnabled: true, aiInsightsProviderName: 'OpenAI' } });
        expect(screen.queryByRole('region')).not.toBeInTheDocument();
        expect(screen.getByTestId('privacy-strip-ai')).toHaveTextContent('Answers may be analysed by AI (OpenAI).');
        unmount();

        const noProvider = renderPanel({ ownerName: 'Acme', settings: { aiInsightsEnabled: true } });
        expect(screen.getByTestId('privacy-strip-ai')).toHaveTextContent(/^Answers may be analysed by AI\.$/);
        noProvider.unmount();

        renderPanel({ ownerName: 'Acme', settings: { aiInsightsEnabled: false, aiInsightsProviderName: 'OpenAI' } });
        expect(screen.queryByTestId('privacy-strip-ai')).not.toBeInTheDocument();
    });

    it('states AI use in the strip in Dutch', () => {
        setBrowserLanguages(['nl']);
        const { unmount } = renderPanel({ ownerName: 'Acme', settings: { aiInsightsEnabled: true, aiInsightsProviderName: 'Mistral' } });
        expect(screen.getByTestId('privacy-strip-ai')).toHaveTextContent('Antwoorden kunnen door AI (Mistral) worden geanalyseerd.');
        unmount();
        renderPanel({ ownerName: 'Acme', settings: { aiInsightsEnabled: true } });
        expect(screen.getByTestId('privacy-strip-ai')).toHaveTextContent(/^Antwoorden kunnen door AI worden geanalyseerd\.$/);
    });

    it('states AI use in Dutch too', () => {
        setBrowserLanguages(['nl']);
        renderPanel({ ownerName: 'Acme', settings: { aiInsightsEnabled: true, aiInsightsProviderName: 'Mistral' } });
        openPanel();
        expect(row('ai')).toHaveTextContent('Je antwoorden kunnen door AI (Mistral) worden geanalyseerd als het team achter dit formulier AI-inzichten gebruikt.');
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

    it("states a date period in the respondent's language", () => {
        setBrowserLanguages(['nl']);
        renderPanel({ ownerName: 'Acme', settings: { responseExpirationType: 'date', responseExpiration: '2027-03-01' } });
        openPanel();
        expect(row('retention')).toHaveTextContent('Bewaard tot 1 maart 2027.');
    });

    it("always states the enforced period, with the creator's explanation next to it", () => {
        setBrowserLanguages(['en']);
        // Text and period: both, the period first. The text never replaces it.
        const { unmount } = renderPanel({ ownerName: 'Acme', settings: { retentionText: 'Kept for 1 year', responseExpirationType: 'days', responseExpiration: '30' } });
        openPanel();
        expect(row('retention')).toHaveTextContent('How long they are keptKept for 30 days after you submit. Kept for 1 year');
        expect(screen.getByTestId('privacy-retention-note')).toHaveTextContent('Kept for 1 year');
        unmount();

        // A period without text: the period alone.
        const second = renderPanel({ ownerName: 'Acme', settings: { retentionText: '   ', responseExpirationType: 'days', responseExpiration: '30' } });
        openPanel();
        expect(row('retention')).toHaveTextContent(/^How long they are keptKept for 30 days after you submit\.$/);
        expect(screen.queryByTestId('privacy-retention-note')).not.toBeInTheDocument();
        second.unmount();

        // Text without a period: "until deleted", then the text.
        setBrowserLanguages(['nl']);
        renderPanel({ ownerName: 'Acme', settings: { retentionText: 'Tot het einde van het project', responseExpirationType: 'forever' } });
        openPanel();
        expect(row('retention')).toHaveTextContent('Geen vaste termijn: bewaard tot ze worden verwijderd. Tot het einde van het project');
    });

    it('says sign-in is required on a private form, in English and Dutch', () => {
        setBrowserLanguages(['en']);
        const { unmount } = renderPanel({ ownerName: 'Acme', settings: { private: true } });
        openPanel();
        expect(row('identity')).toHaveTextContent('You sign in with your email address before you can answer.');
        expect(row('identity')).not.toHaveTextContent(/without signing in/i);
        unmount();

        setBrowserLanguages(['nl']);
        const dutch = renderPanel({ ownerName: 'Acme', settings: { private: true, requireVerifiedIdentity: false } });
        openPanel();
        expect(row('identity')).toHaveTextContent('Je logt in met je e-mailadres voordat je kunt antwoorden.');
        expect(row('identity')).not.toHaveTextContent(/zonder in te loggen/);
        dutch.unmount();

        // A public form without verified identity: no sign-in.
        setBrowserLanguages(['en']);
        renderPanel({ ownerName: 'Acme', settings: { private: false } });
        openPanel();
        expect(row('identity')).toHaveTextContent('No verification needed. You can answer without signing in.');
    });

    it('states AI use without a provider name too', () => {
        setBrowserLanguages(['en']);
        renderPanel({ ownerName: 'Acme', settings: { aiInsightsEnabled: true } });
        openPanel();
        expect(row('ai')).toHaveTextContent("Your answers may be analysed by AI when the form's team runs AI insights.");
    });

    it('links the privacy policy only over http(s)', () => {
        setBrowserLanguages(['en']);
        for (const unsafe of ['javascript:alert(1)', ' JavaScript:alert(1)', 'data:text/html,<b>x</b>', '/privacy']) {
            const { unmount } = renderPanel({ ownerName: 'Acme', settings: { privacyPolicyUrl: unsafe } });
            openPanel();
            expect(screen.queryByRole('link', { name: /privacy policy/i })).not.toBeInTheDocument();
            unmount();
        }
        renderPanel({ ownerName: 'Acme', settings: { privacyPolicyUrl: 'http://acme.test/privacy' } });
        openPanel();
        expect(screen.getByRole('link', { name: /privacy policy/i })).toHaveAttribute('href', 'http://acme.test/privacy');
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
