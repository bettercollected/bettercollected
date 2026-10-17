import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider as JotaiProvider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { DialogModalContainer, START_WITH_AI_DIALOG_CLASS, useDialogModal } from '@app/lib/hooks/use-dialog-modal';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { readBuildReport } from '@app/utils/ai-build-report';
import { FormOutline } from '@app/utils/ai-outline';

import StartWithAi from './start-with-ai-modal';

const outlineMock = vi.fn();
const buildMock = vi.fn();
const replaceMock = vi.fn();
// the workspace's AI setting as the settings query would return it
const ai = { enabled: true, refetch: vi.fn() };

vi.mock('@app/store/redux/form-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useOutlineFormWithAIMutation: () => [outlineMock, { isLoading: false }],
        useBuildFormFromOutlineMutation: () => [buildMock, { isLoading: false }]
    };
});
vi.mock('@app/components/ai/ai-consent', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useWorkspaceAI: () => ({ settings: { enabled: ai.enabled }, enabled: ai.enabled, providerName: 'OpenAI', refetch: () => ai.refetch() }),
        AIOptIn: ({ onEnabled }: { onEnabled?: () => void }) => (
            <div>
                <p>AI is off for this workspace.</p>
                <button
                    type="button"
                    onClick={() => {
                        ai.enabled = true;
                        onEnabled?.();
                    }}
                >
                    Turn AI on
                </button>
            </div>
        )
    };
});
vi.mock('next/navigation', () => ({ usePathname: () => '/acme/dashboard/forms/create' }));
vi.mock('next-nprogress-bar', () => ({ useRouter: () => ({ replace: replaceMock, push: vi.fn() }) }));
vi.mock('next/image', () => ({ default: (props: any) => <span role="img" aria-label={props.alt} /> }));

const OUTLINE: FormOutline = {
    title: 'Volunteer sign-up',
    language: 'en',
    pages: [
        {
            key: 'p1',
            sectionTitle: 'About you',
            questions: [
                { key: 'name', label: 'What is your name?', type: 'short_text', required: true },
                { key: 'email', label: 'What is your email address?', type: 'email', whyWeAsk: 'We send you the rota.' }
            ]
        },
        {
            key: 'p2',
            sectionTitle: 'Helping',
            questions: [
                { key: 'role', label: 'Which task?', type: 'dropdown', choices: ['Stalls', 'Other'] },
                { key: 'other', label: 'Which other task?', type: 'short_text' }
            ]
        }
    ],
    logic: [{ target: 'other', action: 'show', match: 'all', conditions: [{ question: 'role', comparison: 'equals', value: 'Other' }] }],
    jumps: [{ fromPage: 'p1', to: 'end', match: 'all', conditions: [{ question: 'name', comparison: 'is_not_answered' }] }],
    omitted: [{ label: 'Date of birth', reason: 'Not needed.' }]
};

function renderModal() {
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
    render(
        <ReduxProvider store={store}>
            <StartWithAi />
        </ReduxProvider>
    );
}

async function toReview() {
    outlineMock.mockResolvedValue({ data: { outline: structuredClone(OUTLINE) } });
    renderModal();
    fireEvent.change(screen.getByLabelText('Describe the form you need'), { target: { value: 'a volunteer form' } });
    fireEvent.click(screen.getByRole('button', { name: /Draft outline/ }));
    await screen.findByText('Review the outline');
}

describe('Start with AI: outline review', () => {
    beforeEach(() => {
        outlineMock.mockReset();
        buildMock.mockReset();
        replaceMock.mockReset();
        ai.enabled = true;
        ai.refetch = vi.fn();
        sessionStorage.clear();
    });

    it('asks for an outline, not a form, and shows it for review', async () => {
        await toReview();
        expect(outlineMock).toHaveBeenCalledWith({ workspaceId: 'ws-1', body: { prompt: 'a volunteer form' } });
        expect(buildMock).not.toHaveBeenCalled();
        expect(screen.getByLabelText('Form title')).toHaveValue('Volunteer sign-up');
        expect(screen.getByLabelText('Question 1')).toHaveValue('What is your name?');
        expect(screen.getByLabelText('Question 3')).toHaveValue('Which task?');
        expect(screen.getAllByLabelText('Section title').map((input) => (input as HTMLInputElement).value)).toEqual(['About you', 'Helping']);
        expect(screen.getByText(/Why we ask: We send you the rota./)).toBeInTheDocument();
        expect(screen.getByText(/Date of birth: Not needed./)).toBeInTheDocument();
        expect(screen.getByText(/1 show\/hide rule and 1 page jump will be added/)).toBeInTheDocument();
    });

    it('edits the outline and builds exactly what the person kept', async () => {
        await toReview();
        fireEvent.change(screen.getByLabelText('Question 1'), { target: { value: 'Your full name' } });
        fireEvent.change(screen.getAllByLabelText('Section title')[1], { target: { value: 'How you help' } });
        fireEvent.change(screen.getByLabelText('Type of question 2'), { target: { value: 'phone_number' } });
        fireEvent.click(screen.getByRole('button', { name: 'Move Which task? up' }));
        fireEvent.click(screen.getByRole('button', { name: 'Delete Your full name' }));
        fireEvent.click(screen.getByRole('button', { name: 'Delete Which other task?' }));
        fireEvent.click(screen.getByRole('button', { name: 'Add a question to page 2' }));
        // the new question gets the focus, and building waits for its text
        const added = screen.getByLabelText('Question 3');
        expect(added).toHaveFocus();
        expect(screen.getByRole('button', { name: /Build form/ })).toBeDisabled();
        fireEvent.change(added, { target: { value: 'Any questions for us?' } });
        fireEvent.click(screen.getByRole('checkbox', { name: 'Question 3 is required' }));

        buildMock.mockResolvedValue({ data: { formId: 'form-9', title: 'Volunteer sign-up', quality: { score: 100, passed: true, findings: [] }, notes: [] } });
        fireEvent.click(screen.getByRole('button', { name: /Build form/ }));
        await waitFor(() => expect(replaceMock).toHaveBeenCalledWith('/acme/dashboard/forms/form-9/edit'));
        const sent: FormOutline = buildMock.mock.calls[0][0].body.outline;
        expect(sent.pages.map((p) => p.sectionTitle)).toEqual(['About you', 'How you help']);
        expect(sent.pages.map((p) => p.questions.map((q) => [q.label, q.type, !!q.required]))).toEqual([
            [
                ['What is your email address?', 'phone_number', false],
                ['Which task?', 'dropdown', false]
            ],
            [['Any questions for us?', 'short_text', true]]
        ]);
        // the rule and the jump depended on deleted questions
        expect(sent.logic).toEqual([]);
        expect(sent.jumps).toEqual([]);
        // nothing to check: nothing carried to the editor
        expect(readBuildReport('form-9')).toBeNull();
    });

    it('carries notes and findings to the editor, codes and ids only', async () => {
        await toReview();
        const choices = screen.getByLabelText(/Choices, one per line/);
        fireEvent.change(choices, { target: { value: 'Stalls\nCooking\nCleaning' } });
        buildMock.mockResolvedValue({
            data: {
                formId: 'f-1',
                title: 't',
                quality: { score: 80, passed: false, findings: [{ code: 'missing_why_we_ask', severity: 'error', message: 'A question asks for an email', where: ['field-7'] }] },
                notes: ['Suggested choices for 1 question(s).']
            }
        });
        fireEvent.click(screen.getByRole('button', { name: /Build form/ }));
        await waitFor(() => expect(replaceMock).toHaveBeenCalledWith('/acme/dashboard/forms/f-1/edit'));
        expect(buildMock.mock.calls[0][0].body.outline.pages[1].questions[0].choices).toEqual(['Stalls', 'Cooking', 'Cleaning']);
        expect(readBuildReport('f-1')).toEqual({
            notes: ['Suggested choices for 1 question(s).'],
            findings: [{ code: 'missing_why_we_ask', severity: 'error', where: ['field-7'] }]
        });
    });

    it('after ai_not_enabled shows the error inline, refetches the setting and shows AI as off', async () => {
        await toReview();
        ai.refetch = vi.fn(() => {
            ai.enabled = false;
        });
        buildMock.mockResolvedValue({ error: { status: 403, data: { code: 'ai_not_enabled', message: 'AI features are off for this workspace.' } } });
        fireEvent.click(screen.getByRole('button', { name: /Build form/ }));
        expect(await screen.findByRole('alert')).toHaveTextContent('AI features are off for this workspace.');
        expect(ai.refetch).toHaveBeenCalledTimes(1);
        expect(replaceMock).not.toHaveBeenCalled();
        expect(screen.getByRole('button', { name: /Build form/ })).toBeDisabled();
        fireEvent.click(screen.getByRole('button', { name: 'Back to prompt' }));
        expect(screen.getByRole('button', { name: /Draft a new outline/ })).toBeDisabled();
        expect(screen.getByText('AI is off for this workspace.')).toBeInTheDocument();
        expect(screen.queryByText(/sends your prompt/)).not.toBeInTheDocument();
    });

    it.each([
        [502, 'ai_unusable_reply', 'The AI returned an unusable outline.'],
        [429, 'ai_rate_limited', 'Too many AI requests. Please wait a minute and try again.']
    ])('shows a %s outline error inline and stays on the prompt', async (status, code, message) => {
        outlineMock.mockResolvedValue({ error: { status, data: { code, message } } });
        renderModal();
        fireEvent.change(screen.getByLabelText('Describe the form you need'), { target: { value: 'x' } });
        fireEvent.click(screen.getByRole('button', { name: /Draft outline/ }));
        expect(await screen.findByRole('alert')).toHaveTextContent(message);
        expect(screen.getByLabelText('Describe the form you need')).toHaveValue('x');
        expect(ai.refetch).not.toHaveBeenCalled();
        // the next attempt clears it
        outlineMock.mockResolvedValue({ data: { outline: structuredClone(OUTLINE) } });
        fireEvent.click(screen.getByRole('button', { name: /Draft outline/ }));
        await screen.findByText('Review the outline');
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('says nothing more is sent when the outline has no gaps', async () => {
        await toReview();
        expect(screen.queryByRole('checkbox', { name: 'Let AI fill in missing choices and reasons' })).not.toBeInTheDocument();
        expect(screen.queryByText(/Build form sends/)).not.toBeInTheDocument();
        buildMock.mockResolvedValue({ data: { formId: 'f-2', title: 't', quality: { score: 100, passed: true, findings: [] }, notes: [] } });
        fireEvent.click(screen.getByRole('button', { name: /Build form/ }));
        await waitFor(() => expect(buildMock).toHaveBeenCalled());
        expect(buildMock.mock.calls[0][0].body.fillGaps).toBe(false);
    });

    it('asks before sending pages with gaps, and sends nothing when told not to', async () => {
        await toReview();
        fireEvent.change(screen.getByLabelText(/Choices, one per line/), { target: { value: '' } });
        const allow = screen.getByRole('checkbox', { name: 'Let AI fill in missing choices and reasons' });
        expect(allow).toBeChecked();
        expect(screen.getByText('Build form sends pages that are missing choices or a reason, together with your workspace AI profile, to OpenAI, so it can suggest them.')).toBeInTheDocument();

        fireEvent.click(allow);
        expect(allow).not.toBeChecked();
        expect(screen.getByText(/Build form sends nothing to the AI/)).toBeInTheDocument();
        expect(screen.queryByText(/so it can suggest them/)).not.toBeInTheDocument();
        buildMock.mockResolvedValue({ data: { formId: 'f-3', title: 't', quality: { score: 100, passed: true, findings: [] }, notes: [] } });
        fireEvent.click(screen.getByRole('button', { name: /Build form/ }));
        await waitFor(() => expect(buildMock).toHaveBeenCalledTimes(1));
        expect(buildMock.mock.calls[0][0].body.fillGaps).toBe(false);
    });

    it('lets the AI fill gaps by default', async () => {
        await toReview();
        // an identity question without a reason is a gap too
        fireEvent.change(screen.getByLabelText('Question 1'), { target: { value: 'What is your passport number?' } });
        expect(screen.getByRole('checkbox', { name: 'Let AI fill in missing choices and reasons' })).toBeChecked();
        buildMock.mockResolvedValue({ data: { formId: 'f-4', title: 't', quality: { score: 100, passed: true, findings: [] }, notes: [] } });
        fireEvent.click(screen.getByRole('button', { name: /Build form/ }));
        await waitFor(() => expect(buildMock).toHaveBeenCalledTimes(1));
        expect(buildMock.mock.calls[0][0].body.fillGaps).toBe(true);
    });

    it('goes back to the prompt and returns to the same outline', async () => {
        await toReview();
        fireEvent.change(screen.getByLabelText('Question 1'), { target: { value: 'Changed' } });
        fireEvent.click(screen.getByRole('button', { name: 'Back to prompt' }));
        expect(screen.getByRole('button', { name: /Draft a new outline/ })).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Back to the outline you were reviewing' }));
        expect(screen.getByLabelText('Question 1')).toHaveValue('Changed');
    });
});

describe('OutlineReview list', () => {
    beforeEach(() => {
        ai.enabled = true;
    });

    it('is a list of labelled controls per page', async () => {
        await toReview();
        const pages = screen.getAllByRole('region');
        expect(pages).toHaveLength(2);
        expect(within(pages[0]).getAllByRole('listitem')).toHaveLength(2);
        expect(within(pages[0]).getByRole('button', { name: 'Move What is your name? up' })).toBeDisabled();
    });

    it('says which rules and jumps a deletion drops, and undoes it', async () => {
        await toReview();
        fireEvent.click(screen.getByRole('button', { name: 'Delete Which task?' }));
        expect(screen.getByText('Question deleted. 1 rule that used this question was dropped.')).toBeInTheDocument();
        expect(screen.getByText(/1 page jump will be added/)).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
        expect(screen.getByLabelText('Question 3')).toHaveValue('Which task?');
        expect(screen.getByText(/1 show\/hide rule and 1 page jump will be added/)).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Undo' })).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Delete What is your name?' }));
        expect(screen.getByText('Question deleted. 1 jump that used this question was dropped.')).toBeInTheDocument();
        // the next edit ends the chance to undo
        fireEvent.change(screen.getByLabelText('Question 1'), { target: { value: 'Email' } });
        expect(screen.queryByRole('button', { name: 'Undo' })).not.toBeInTheDocument();
    });
});

describe('Start with AI: errors, hints and layout', () => {
    beforeEach(() => {
        outlineMock.mockReset();
        buildMock.mockReset();
        ai.enabled = true;
        ai.refetch = vi.fn();
    });

    it('drops the "AI is off" error once AI is turned on again', async () => {
        ai.refetch = vi.fn(() => {
            ai.enabled = false;
        });
        outlineMock.mockResolvedValue({ error: { status: 403, data: { code: 'ai_not_enabled', message: 'AI features are off for this workspace.' } } });
        renderModal();
        fireEvent.change(screen.getByLabelText('Describe the form you need'), { target: { value: 'a form' } });
        fireEvent.click(screen.getByRole('button', { name: /Draft outline/ }));
        expect(await screen.findByRole('alert')).toHaveTextContent('AI features are off');
        expect(screen.getByRole('button', { name: /Draft outline/ })).toBeDisabled();

        fireEvent.click(screen.getByRole('button', { name: 'Turn AI on' }));
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Draft outline/ })).toBeEnabled();
    });

    it('the choices hint follows the fill-in choice', async () => {
        await toReview();
        fireEvent.change(screen.getByLabelText(/Choices, one per line/), { target: { value: '' } });
        expect(screen.getByText(/left empty, the AI suggests some when you build/)).toBeInTheDocument();
        fireEvent.click(screen.getByRole('checkbox', { name: 'Let AI fill in missing choices and reasons' }));
        expect(screen.getByText(/left empty, it is asked as short text/)).toBeInTheDocument();
        expect(screen.queryByText(/the AI suggests some/)).not.toBeInTheDocument();
    });

    it('the fill-in checkbox is described by its notice', async () => {
        await toReview();
        fireEvent.change(screen.getByLabelText(/Choices, one per line/), { target: { value: '' } });
        const allow = screen.getByRole('checkbox', { name: 'Let AI fill in missing choices and reasons' });
        expect(allow).toHaveAttribute('aria-describedby', 'outline-fill-gaps-notice');
        expect(allow).toHaveAccessibleDescription(/Build form sends pages that are missing choices or a reason/);
        fireEvent.click(allow);
        expect(allow).toHaveAccessibleDescription(/Build form sends nothing to the AI/);
    });

    it('shows the Undo notice outside the scrolling list', async () => {
        await toReview();
        fireEvent.click(screen.getByRole('button', { name: 'Delete Which other task?' }));
        const undo = screen.getByRole('button', { name: 'Undo' });
        expect(within(screen.getByTestId('outline-scroll')).queryByRole('button', { name: 'Undo' })).not.toBeInTheDocument();
        expect(undo.closest('[aria-live="polite"]')).not.toBeNull();
    });

    it('moves focus to Undo after a deletion, and the empty live region takes no space', async () => {
        await toReview();
        const live = screen
            .getByRole('button', { name: /Build form/ })
            .closest('[data-testid="start-with-ai-review"]')!
            .querySelector('[aria-live="polite"]')!;
        // mounted while empty, and not an item of the spaced footer column
        expect(live).toBeEmptyDOMElement();
        expect(live.parentElement!.className).not.toContain('gap-');
        fireEvent.click(screen.getByRole('button', { name: 'Delete What is your email address?' }));
        expect(screen.getByRole('button', { name: 'Undo' })).toHaveFocus();
        expect(live).not.toBeEmptyDOMElement();
    });

    it('question text wraps in a growing field', async () => {
        await toReview();
        const text = screen.getByLabelText('Question 1');
        expect(text.tagName).toBe('TEXTAREA');
        fireEvent.change(text, { target: { value: 'A long question\nthat was pasted' } });
        expect(screen.getByLabelText('Question 1')).toHaveValue('A long question that was pasted');
    });

    it('fits the screen: a capped dialog where only the outline list scrolls', async () => {
        expect(START_WITH_AI_DIALOG_CLASS.split(' ')).toEqual(expect.arrayContaining(['flex', 'flex-col', 'overflow-hidden', 'max-h-[calc(100dvh-2rem)]']));

        function Opener() {
            const { openDialogModal } = useDialogModal();
            React.useEffect(() => openDialogModal('START_WITH_AI'), []);
            return null;
        }
        outlineMock.mockResolvedValue({ data: { outline: structuredClone(OUTLINE) } });
        store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
        render(
            <ReduxProvider store={store}>
                <JotaiProvider>
                    <Opener />
                    <DialogModalContainer />
                </JotaiProvider>
            </ReduxProvider>
        );
        const dialog = await screen.findByRole('dialog', { name: 'Start with AI' });
        expect(dialog.className).toContain('max-h-[calc(100dvh-2rem)]');
        expect(dialog.className).toContain('overflow-hidden');
        fireEvent.change(within(dialog).getByLabelText('Describe the form you need'), { target: { value: 'a form' } });
        fireEvent.click(within(dialog).getByRole('button', { name: /Draft outline/ }));
        await within(dialog).findByText('Review the outline');
        const review = within(dialog).getByTestId('start-with-ai-review');
        expect(review.className.split(' ')).toEqual(expect.arrayContaining(['flex', 'min-h-0', 'flex-1', 'flex-col']));
        const list = within(dialog).getByTestId('outline-scroll');
        expect(list.className.split(' ')).toEqual(expect.arrayContaining(['min-h-0', 'flex-1', 'overflow-y-auto']));
        // header and footer stay out of the scrolling part
        expect(list.contains(within(dialog).getByRole('button', { name: /Build form/ }))).toBe(false);
        expect(list.contains(within(dialog).getByLabelText('Form title'))).toBe(false);
        expect(list.contains(within(dialog).getByLabelText('Question 1'))).toBe(true);
    });
});
