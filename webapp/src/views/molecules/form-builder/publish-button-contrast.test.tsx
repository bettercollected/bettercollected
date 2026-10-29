import React from 'react';

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import i18n from 'i18next';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';
import { PublishProblem, splitPublishProblems, themeContrastProblems } from '@app/utils/publish-checks';

import enBuilder from '../../../../public/locales/en/builder.json';
import nlBuilder from '../../../../public/locales/nl/builder.json';
import PublishButton, { PublishProblemsDialog } from './publish-button';

const en = (enBuilder as any).PUBLISH_CONTRAST;
const nl = (nlBuilder as any).PUBLISH_CONTRAST;

const publishFormMock = vi.fn();
const readPublishedMock = vi.fn();
vi.mock('@app/store/redux/form-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, usePublishV2FormMutation: () => [publishFormMock, { isLoading: false }], useLazyGetPublishedFormQuery: () => [readPublishedMock] };
});
vi.mock('@app/lib/hooks/use-dialog-modal', () => ({ useDialogModal: () => ({ openDialogModal: vi.fn() }) }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => '/ws/dashboard/forms/form-1/edit' }));
vi.mock('@app/views/molecules/form-builder/audo-save-form', () => ({ flushAutosave: async () => 'saved' }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: () => false, permissions: new Set(), isLoading: false, ready: true }) }));
vi.mock('@Components/modals/contexts/bottom-sheet-modal-context', () => ({ useBottomSheetModal: () => ({ openBottomSheetModal: vi.fn(), closeBottomSheetModal: vi.fn() }) }));

const PAGE = [{ id: 'page-1', index: 0, type: 'slide', properties: { fields: [{ id: 'q-1', index: 0, type: 'short_text', title: 'Name', description: '' }] } }];
// Hard to read: grey questions and pale borders on white.
const PASTEL = { title: 'Pastel', primary: '#9CA3AF', secondary: '#1649E2', tertiary: '#E5E7EB', accent: '#FFFFFF' };
const PALE = { ...PASTEL, title: 'Pale', primary: '#B0B7C3' };
const READABLE = { title: 'Readable', primary: '#101828', secondary: '#1649E2', tertiary: '#6B7280', accent: '#FFFFFF' };

const setUp = (publishChecksVersion: number | null, theme: Record<string, unknown>) => {
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme', title: 'Acme' } as any));
    store.dispatch(setForm({ formId: 'form-1', title: 'Sign-up', fields: PAGE, settings: { publishChecksVersion }, theme, thankyouPage: [{ id: 'end-1', name: 'Thanks' }] } as any));
};

function renderButton() {
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <PublishButton />
            </Provider>
        </ReduxProvider>
    );
}

const clickPublish = async () => {
    await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
    });
};

const published = () => expect(publishFormMock).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: 'form-1' });

describe('an older form whose colours are hard to read', () => {
    beforeEach(() => {
        publishFormMock.mockReset().mockResolvedValue({ data: { formId: 'form-1' } });
        readPublishedMock.mockReset();
    });
    afterEach(async () => {
        await i18n.changeLanguage('en');
    });

    for (const version of [2, 1, null]) {
        it(`only advises when it is live with those colours (checks version ${version}), and publishes on "Publish anyway"`, async () => {
            readPublishedMock.mockResolvedValue({ data: { formId: 'form-1', theme: PASTEL } });
            setUp(version, PASTEL);
            renderButton();
            await clickPublish();
            const dialog = await screen.findByRole('dialog', { name: 'Before you publish' });
            expect(readPublishedMock).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: 'form-1' }, false);
            expect(screen.queryByTestId('publish-problems')).not.toBeInTheDocument();
            expect(screen.getByTestId('publish-recommendations')).toHaveTextContent('The theme’s colours are hard to read'.replace('’', "'"));
            expect(screen.getByTestId('publish-recommendations')).toHaveTextContent('can still be published as it is');
            expect(dialog).toHaveTextContent(en.INTRO);
            expect(publishFormMock).not.toHaveBeenCalled();
            await act(async () => {
                fireEvent.click(screen.getByRole('button', { name: 'Publish anyway' }));
            });
            await waitFor(published);
        });
    }

    it('blocks once its colours differ from the live ones, with no way to publish from the dialog', async () => {
        readPublishedMock.mockResolvedValue({ data: { formId: 'form-1', theme: PASTEL } });
        setUp(2, PALE);
        renderButton();
        await clickPublish();
        await screen.findByRole('dialog', { name: 'Before you publish' });
        expect(screen.getByTestId('publish-problems')).toHaveTextContent('hard to read');
        expect(screen.queryByTestId('publish-recommendations')).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Publish anyway' })).not.toBeInTheDocument();
        expect(publishFormMock).not.toHaveBeenCalled();
    });

    it('blocks a form that was never published (no live version to compare with)', async () => {
        readPublishedMock.mockResolvedValue({ error: { status: 404 } });
        setUp(null, PASTEL);
        renderButton();
        await clickPublish();
        await screen.findByRole('dialog', { name: 'Before you publish' });
        expect(screen.getByTestId('publish-problems')).toHaveTextContent('hard to read');
        expect(publishFormMock).not.toHaveBeenCalled();
    });

    it('leaves the decision to the server when the live colours cannot be read, and shows what it refuses', async () => {
        readPublishedMock.mockResolvedValue({ error: { status: 500 } });
        publishFormMock.mockResolvedValue({ error: { status: 422, data: { code: 'form_not_publishable', problems: [{ code: 'theme_contrast', fieldId: 'theme', message: "The theme's colours are hard to read: input borders." }] } } });
        setUp(2, PASTEL);
        renderButton();
        await clickPublish();
        // nothing was claimed here: the click went to the server
        await waitFor(published);
        const dialog = await screen.findByRole('dialog', { name: 'Before you publish' });
        expect(dialog).toHaveTextContent('hard to read');
        expect(screen.getByTestId('publish-problems')).toBeInTheDocument();
    });

    it('does not read the live version for a theme that reads, or for a new form', async () => {
        setUp(2, READABLE);
        const view = renderButton();
        await clickPublish();
        await waitFor(published);
        expect(readPublishedMock).not.toHaveBeenCalled();
        view.unmount();

        publishFormMock.mockClear();
        setUp(3, PASTEL);
        renderButton();
        await clickPublish();
        await screen.findByRole('dialog', { name: 'Before you publish' });
        expect(screen.getByTestId('publish-problems')).toHaveTextContent('hard to read');
        expect(readPublishedMock).not.toHaveBeenCalled();
        expect(publishFormMock).not.toHaveBeenCalled();
    });
});

describe('the advice about an older form’s colours, in the dialog', () => {
    afterEach(async () => {
        await i18n.changeLanguage('en');
    });
    const advice = splitPublishProblems(themeContrastProblems({ ...PASTEL, secondary: '#F5C242', buttonStyle: 'outlined' } as any, 'advisory'), 2).recommended as PublishProblem[];
    const renderAdvice = (onShow = vi.fn(), onPublishAnyway = vi.fn()) => {
        const view = render(<PublishProblemsDialog blocking={[]} recommended={advice} onClose={vi.fn()} onPublishAnyway={onPublishAnyway} onShowQuestion={onShow} canShowQuestion={() => true} />);
        return { view, onShow, onPublishAnyway };
    };

    it('names the failing pairings in the builder’s words, including the outlined button', () => {
        renderAdvice();
        const list = screen.getByTestId('publish-recommendations');
        expect(list).toHaveTextContent('questions and text on the page');
        expect(list).toHaveTextContent('text and edges of outlined buttons');
        expect(list).not.toHaveTextContent('white text on buttons');
        expect(list).toHaveTextContent(en.ADVISORY.split('{{pairs}}')[1].trim().slice(0, 30));
    });

    it('leads to the theme and still offers to publish', () => {
        const { onShow, onPublishAnyway } = renderAdvice();
        fireEvent.click(screen.getByRole('button', { name: en.SHOW }));
        expect(onShow).toHaveBeenCalledWith('theme');
        fireEvent.click(screen.getByRole('button', { name: 'Publish anyway' }));
        expect(onPublishAnyway).toHaveBeenCalledTimes(1);
    });

    it('is worded in Dutch, addressing the reader as "u"', async () => {
        await act(async () => {
            await i18n.changeLanguage('nl');
        });
        renderAdvice();
        const list = screen.getByTestId('publish-recommendations');
        expect(list).toHaveTextContent('vragen en tekst op de pagina');
        expect(list).toHaveTextContent('tekst en randen van omlijnde knoppen');
        expect(list).toHaveTextContent(nl.ADVISORY.split('{{pairs}}')[1].trim().slice(0, 30));
        expect(screen.getByRole('button', { name: nl.SHOW })).toBeInTheDocument();
        expect(screen.getByText(nl.INTRO)).toBeInTheDocument();
        expect(`${nl.ADVISORY} ${nl.INTRO}`).toMatch(/\bu\b/);
        expect(`${nl.ADVISORY} ${nl.INTRO}`).not.toMatch(/\b(je|jouw|jij)\b/i);
    });

    it('has no accessibility violations, in English or Dutch', async () => {
        renderAdvice();
        expect(await axeViolations(document.body)).toEqual([]);
        cleanup();
        await act(async () => {
            await i18n.changeLanguage('nl');
        });
        renderAdvice();
        expect(await axeViolations(document.body)).toEqual([]);
    });

    it('has the same keys in English and Dutch', () => {
        expect(Object.keys(nl).sort()).toEqual(Object.keys(en).sort());
        expect((nlBuilder as any).THEME.CONTRAST_ISSUE_OUTLINED).toBeTruthy();
        expect((enBuilder as any).THEME.CONTRAST_ISSUE_OUTLINED).toBeTruthy();
    });
});

describe('the colour advice beside a "why we ask this" recommendation', () => {
    afterEach(async () => {
        await i18n.changeLanguage('en');
    });
    const reason: PublishProblem = { code: 'missing_why_we_ask', fieldId: 'e', message: '"Email" asks for personal details.' };
    const recommended = [reason, ...(splitPublishProblems(themeContrastProblems(PASTEL, 'advisory'), 2).recommended as PublishProblem[])];
    const renderBoth = () => render(<PublishProblemsDialog blocking={[]} recommended={recommended} onClose={vi.fn()} onPublishAnyway={vi.fn()} onShowQuestion={vi.fn()} canShowQuestion={() => true} />);

    it('keeps each item\'s own context: a neutral intro, the reason item says why it matters', () => {
        renderBoth();
        const list = screen.getByTestId('publish-recommendations');
        expect(screen.getByText(en.INTRO)).toBeInTheDocument();
        expect(screen.queryByText(en.WHY_WE_ASK_INTRO)).not.toBeInTheDocument();
        expect(list).toHaveTextContent('"Email" asks for personal details.');
        expect(list).toHaveTextContent(en.WHY_WE_ASK_CONTEXT);
        expect(list).toHaveTextContent('can still be published as it is');
        expect(screen.getAllByRole('listitem')).toHaveLength(2);
    });

    it('is the same in Dutch', async () => {
        await act(async () => {
            await i18n.changeLanguage('nl');
        });
        renderBoth();
        const list = screen.getByTestId('publish-recommendations');
        expect(screen.getByText(nl.INTRO)).toBeInTheDocument();
        expect(list).toHaveTextContent(nl.WHY_WE_ASK_CONTEXT);
        expect(list).toHaveTextContent('De kleuren van het thema zijn slecht leesbaar');
        expect(`${nl.WHY_WE_ASK_INTRO} ${nl.WHY_WE_ASK_CONTEXT}`).not.toMatch(/\b(je|jouw|jij)\b/i);
    });

    it('keeps the reason intro when it is alone, and no context line then', () => {
        render(<PublishProblemsDialog blocking={[]} recommended={[reason]} onClose={vi.fn()} onPublishAnyway={vi.fn()} onShowQuestion={vi.fn()} canShowQuestion={() => true} />);
        expect(screen.getByText(en.WHY_WE_ASK_INTRO)).toBeInTheDocument();
        expect(screen.getByTestId('publish-recommendations')).not.toHaveTextContent(en.WHY_WE_ASK_CONTEXT);
    });

    it('has no accessibility violations', async () => {
        renderBoth();
        expect(await axeViolations(document.body)).toEqual([]);
    });
});
