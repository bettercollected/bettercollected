import { readFileSync } from 'fs';
import { resolve } from 'path';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { afterEach, describe, expect, it, vi } from 'vitest';

import I18nProvider from '@app/shared/hocs/i18n-provider';
import { contrast } from '@app/utils/color-contrast';
import { ownerProps } from '@app/utils/workspace-display-name';

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

    it('never opens by default over the primary action, and leaves a respondent-toggled panel alone', () => {
        setBrowserLanguages(['en']);
        // A welcome page whose Start button sits 700px down an 860px area: an
        // open panel (any height, here measured as 0 in jsdom, so force it)
        // would not leave room.
        const page = document.createElement('div');
        page.innerHTML = '<div data-fit-area><div><div data-primary-content><button data-primary-action>Start</button></div></div></div>';
        document.body.appendChild(page);
        const content = page.querySelector('[data-primary-content]') as HTMLElement;
        const action = page.querySelector('[data-primary-action]') as HTMLElement;
        content.getBoundingClientRect = () => ({ top: 0, bottom: 900 }) as DOMRect;
        action.getBoundingClientRect = () => ({ top: 850, bottom: 900 }) as DOMRect;
        Object.defineProperty(page.querySelector('[data-fit-area]')!, 'clientHeight', { value: 860 });

        render(<TrustLayer ownerName="Acme" defaultExpanded protectPrimaryAction />, { wrapper: Wrapper });
        expect(screen.queryByRole('region')).not.toBeInTheDocument();
        // The respondent can still open it.
        fireEvent.click(screen.getByRole('button', { name: 'Your privacy' }));
        expect(screen.getByRole('region')).toBeInTheDocument();
        page.remove();
    });

    it('opens by default with the primary action protected when it fits', () => {
        setBrowserLanguages(['en']);
        render(<TrustLayer ownerName="Acme" defaultExpanded protectPrimaryAction />, { wrapper: Wrapper });
        // No primary action on the page: nothing to protect.
        expect(screen.getByRole('region')).toBeInTheDocument();
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
        expect(row('retention')).toHaveTextContent('90 days after you submit.');
        expect(row('identity')).toHaveTextContent('You sign in with your email address before you can answer.');
        expect(row('rights')).toHaveTextContent('You can view your answers and ask for them to be deleted at any time.');
        expect(within(row('rights')).getByRole('link', { name: /view or delete your response/i })).toHaveAttribute('href', 'https://forms.test/acme');
    });

    it('labels its rows in small text that meets 4.5:1 on the white panel (WCAG 1.4.3)', () => {
        renderPanel({ ownerName: 'Acme Health', settings: {} });
        openPanel();
        const term = row('receiver').querySelector('dt')!;
        expect(term.className).toContain('text-black-600');
        // The token's value, from the theme; measured in Chrome too (4.97:1 on #FFFFFF).
        const css = readFileSync(resolve(__dirname, '../../../assets/css/tailwind.css'), 'utf8');
        const black600 = css.match(/--color-black-600:\s*(#[0-9a-fA-F]{6})/)![1];
        expect(contrast(black600, '#FFFFFF')).toBeGreaterThanOrEqual(4.5);
    });

    it('says whose form it is in words when the workspace has no name, never its id', () => {
        const id = '65f1c0a2b3d4e5f607182930';
        // What the form pages pass for a loaded workspace without a usable name.
        const unnamed = { id: 'ws1', title: '', workspaceName: id, ownerId: id };
        setBrowserLanguages(['en-GB']);
        const { unmount } = renderPanel({ ...ownerProps(unnamed) });
        expect(screen.getByText(/Collected by/)).toHaveTextContent('Collected by the owner of this form');
        fireEvent.click(screen.getByRole('button', { name: /your privacy/i }));
        expect(row('receiver')).toHaveTextContent('Who receives your answersThe owner of this form');
        expect(document.body).not.toHaveTextContent(id);
        unmount();

        setBrowserLanguages(['nl-NL']);
        renderPanel({ ...ownerProps(unnamed) });
        expect(screen.getByText(/Verzameld door/)).toHaveTextContent('Verzameld door de eigenaar van dit formulier');
        fireEvent.click(screen.getByRole('button', { name: /je privacy/i }));
        expect(row('receiver')).toHaveTextContent('Wie je antwoorden ontvangtDe eigenaar van dit formulier');
        expect(document.body).not.toHaveTextContent(id);
    });

    it('claims no owner while the workspace is still loading', () => {
        setBrowserLanguages(['en-GB']);
        // The store's initial workspace: no id, no title, no handle yet.
        renderPanel({ ...ownerProps({ id: '', title: '', workspaceName: '' }) });
        expect(screen.queryByText(/Collected by/)).toBeNull();
        fireEvent.click(screen.getByRole('button', { name: /your privacy/i }));
        expect(screen.queryByTestId('privacy-receiver')).toBeNull();
        expect(document.body).not.toHaveTextContent(/owner of this form/i);
    });

    it('still names the workspace when it has a title or a readable handle', () => {
        setBrowserLanguages(['en-GB']);
        renderPanel({ ...ownerProps({ id: 'ws1', title: '', workspaceName: 'acme-health' }) });
        expect(screen.getByText(/Collected by/)).toHaveTextContent('Collected by acme-health');
    });

    it('speaks Dutch to a Dutch browser', () => {
        setBrowserLanguages(['nl-NL', 'en']);
        renderPanel({ ownerName: 'Vereniging Voorbeeld', settings: { purpose: 'Om uw afspraak te plannen', responseExpirationType: 'days', responseExpiration: '1' } });
        expect(screen.getByText(/Verzameld door/)).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: /je privacy/i }));
        expect(screen.getByRole('heading', { name: 'Wat er met je antwoorden gebeurt' })).toBeInTheDocument();
        expect(row('receiver')).toHaveTextContent('Wie je antwoorden ontvangt');
        expect(row('retention')).toHaveTextContent('1 dag na het insturen.');
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
        expect(row('retention')).toHaveTextContent('No fixed period. They are kept until they are deleted.');
        unmount();

        setBrowserLanguages(['nl']);
        renderPanel({ ownerName: 'Acme', settings: {} });
        openPanel();
        expect(row('retention')).toHaveTextContent('Geen vaste termijn. Ze worden bewaard tot ze worden verwijderd.');
    });

    it("states a date period in the respondent's language", () => {
        setBrowserLanguages(['nl']);
        renderPanel({ ownerName: 'Acme', settings: { responseExpirationType: 'date', responseExpiration: '2027-03-01' } });
        openPanel();
        expect(row('retention')).toHaveTextContent('Tot 1 maart 2027.');
    });

    // Every shape the retention setting can have, with the one sentence it
    // must read (the backend applies it the same way: services/retention.py).
    const RETENTION_SHAPES: Array<{ shape: string; settings: Record<string, unknown>; en: string; nl: string }> = [
        { shape: 'no setting', settings: {}, en: 'No fixed period. They are kept until they are deleted.', nl: 'Geen vaste termijn. Ze worden bewaard tot ze worden verwijderd.' },
        { shape: 'forever', settings: { responseExpirationType: 'forever' }, en: 'No fixed period. They are kept until they are deleted.', nl: 'Geen vaste termijn. Ze worden bewaard tot ze worden verwijderd.' },
        { shape: 'forever with a stale value', settings: { responseExpirationType: 'forever', responseExpiration: '30' }, en: 'No fixed period. They are kept until they are deleted.', nl: 'Geen vaste termijn. Ze worden bewaard tot ze worden verwijderd.' },
        { shape: 'a value without a type', settings: { responseExpiration: '30' }, en: 'No fixed period. They are kept until they are deleted.', nl: 'Geen vaste termijn. Ze worden bewaard tot ze worden verwijderd.' },
        { shape: 'days', settings: { responseExpirationType: 'days', responseExpiration: '30' }, en: '30 days after you submit.', nl: '30 dagen na het insturen.' },
        { shape: 'one day', settings: { responseExpirationType: 'days', responseExpiration: '1' }, en: '1 day after you submit.', nl: '1 dag na het insturen.' },
        { shape: 'days out of range', settings: { responseExpirationType: 'days', responseExpiration: '99999' }, en: 'No fixed period. They are kept until they are deleted.', nl: 'Geen vaste termijn. Ze worden bewaard tot ze worden verwijderd.' },
        { shape: 'unreadable days', settings: { responseExpirationType: 'days', responseExpiration: '6 months' }, en: 'No fixed period. They are kept until they are deleted.', nl: 'Geen vaste termijn. Ze worden bewaard tot ze worden verwijderd.' },
        { shape: 'a date', settings: { responseExpirationType: 'date', responseExpiration: '2027-03-01' }, en: 'Until 1 March 2027.', nl: 'Tot 1 maart 2027.' },
        { shape: 'a stored timestamp', settings: { responseExpirationType: 'date', responseExpiration: '2027-03-01T00:00:00.000Z' }, en: 'Until 1 March 2027.', nl: 'Tot 1 maart 2027.' },
        { shape: 'an unreadable date', settings: { responseExpirationType: 'date', responseExpiration: 'next spring' }, en: 'No fixed period. They are kept until they are deleted.', nl: 'Geen vaste termijn. Ze worden bewaard tot ze worden verwijderd.' }
    ];

    describe.each(RETENTION_SHAPES)('retention: $shape', ({ settings, en, nl }) => {
        // The creator's own words, a period that disagrees with every shape:
        // they are not shown, so the panel states one thing.
        it.each([
            ['en', en],
            ['nl', nl]
        ])('states exactly one period in %s', (language, sentence) => {
            setBrowserLanguages([language]);
            renderPanel({ ownerName: 'Acme', settings: { ...settings, retentionText: 'kept for 6 months' } });
            openPanel();
            const term = language === 'nl' ? 'Hoe lang ze bewaard worden' : 'How long they are kept';
            expect(row('retention').textContent).toBe(`${term}${sentence}`);
            expect(row('retention')).not.toHaveTextContent(/6 months/);
            expect(screen.queryByTestId('privacy-retention-note')).not.toBeInTheDocument();
        });
    });

    it('does not show the creator note beside the period, in any theme', () => {
        setBrowserLanguages(['en']);
        renderPanel({ ownerName: 'Acme', settings: { retentionText: 'Kept for 1 year', responseExpirationType: 'days', responseExpiration: '30' } });
        openPanel();
        expect(row('retention').querySelector('dd')!.textContent).toBe('30 days after you submit.');
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

describe('Privacy panel: answers also sent to a case system', () => {
    afterEach(() => {
        vi.restoreAllMocks();
        window.history.replaceState(null, '', '/');
    });

    it('says nothing about a case system when the form does not send to one', () => {
        setBrowserLanguages(['en']);
        const { unmount } = renderPanel({ ownerName: 'Acme' });
        openPanel();
        expect(screen.queryByTestId('privacy-registration')).not.toBeInTheDocument();
        expect(screen.queryByText(/case system/i)).not.toBeInTheDocument();
        expect(screen.queryByText(/does not delete the copy/i)).not.toBeInTheDocument();
        unmount();
        // an empty destination is no destination
        renderPanel({ ownerName: 'Acme', registrationDestination: { organisation: '   ' } });
        openPanel();
        expect(screen.queryByTestId('privacy-registration')).not.toBeInTheDocument();
        expect(screen.queryByText(/case system/i)).not.toBeInTheDocument();
    });

    it('names the organisation whose case system also receives the answers (English)', () => {
        setBrowserLanguages(['en']);
        renderPanel({ ownerName: 'Acme', registrationDestination: { organisation: 'Example Organisation' } });
        openPanel();
        expect(row('registration')).toHaveTextContent("Your answers are also sent to Example Organisation's case system.");
        // and what deleting here does not do, and who to ask
        expect(row('registration')).toHaveTextContent('Deleting your answers here does not delete the copy at Example Organisation. Contact Example Organisation to have it deleted.');
        // before the rights: what leaves, then what the respondent can do
        const keys = screen.getAllByTestId(/^privacy-/).map((el) => el.getAttribute('data-testid'));
        expect(keys.indexOf('privacy-registration')).toBeLessThan(keys.indexOf('privacy-rights'));
    });

    it('says it in Dutch to a Dutch browser, in the same "je" register', () => {
        setBrowserLanguages(['nl-NL']);
        renderPanel({ ownerName: 'Acme', registrationDestination: { organisation: 'Voorbeeld Organisatie' } });
        fireEvent.click(screen.getByRole('button', { name: /je privacy/i }));
        expect(row('registration')).toHaveTextContent('Je antwoorden worden ook verstuurd naar het zaaksysteem van Voorbeeld Organisatie.');
        expect(row('registration')).toHaveTextContent('Als je je antwoorden hier verwijdert, wordt de kopie bij Voorbeeld Organisatie niet verwijderd. Neem daarvoor contact op met Voorbeeld Organisatie.');
    });

    it('renders an organisation name with markup as literal text', () => {
        setBrowserLanguages(['en']);
        const name = '<img src=x onerror="window.__pwned=1"><b>Acme</b>';
        renderPanel({ ownerName: 'Acme', registrationDestination: { organisation: name } });
        openPanel();
        const line = row('registration');
        expect(line.querySelector('img')).toBeNull();
        expect(line.querySelector('b')).toBeNull();
        expect(line).toHaveTextContent(`Your answers are also sent to ${name}'s case system.`);
        expect(line).toHaveTextContent(`Contact ${name} to have it deleted.`);
        expect((window as any).__pwned).toBeUndefined();
    });
});
