import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { FormOutline } from '@app/utils/ai-outline';

import StartWithAi from './start-with-ai-modal';

const outlineMock = vi.fn();
const buildMock = vi.fn();
const replaceMock = vi.fn();
const toastMock = vi.fn();

vi.mock('@app/store/redux/form-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useOutlineFormWithAIMutation: () => [outlineMock, { isLoading: false }],
        useBuildFormFromOutlineMutation: () => [buildMock, { isLoading: false }]
    };
});
vi.mock('@app/components/ai/ai-consent', () => ({
    useWorkspaceAI: () => ({ settings: { enabled: true }, enabled: true, providerName: 'OpenAI' }),
    AIOptIn: () => null
}));
vi.mock('next-nprogress-bar', () => ({ useRouter: () => ({ replace: replaceMock, push: vi.fn() }) }));
vi.mock('next/image', () => ({ default: (props: any) => <img alt={props.alt} /> }));
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast: toastMock }) }));

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
        { key: 'p2', sectionTitle: 'Helping', questions: [{ key: 'role', label: 'Which task?', type: 'dropdown', choices: ['Stalls', 'Other'] }] }
    ],
    logic: [],
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
        toastMock.mockReset();
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
        expect(screen.getByText(/1 page jump will be added/)).toBeInTheDocument();
    });

    it('edits the outline and builds exactly what the person kept', async () => {
        await toReview();
        fireEvent.change(screen.getByLabelText('Question 1'), { target: { value: 'Your full name' } });
        fireEvent.change(screen.getAllByLabelText('Section title')[1], { target: { value: 'How you help' } });
        fireEvent.change(screen.getByLabelText('Type of question 2'), { target: { value: 'phone_number' } });
        fireEvent.click(screen.getByRole('button', { name: 'Move Which task? up' }));
        fireEvent.click(screen.getByRole('button', { name: 'Delete Your full name' }));
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
        // the jump depended on the deleted question
        expect(sent.jumps).toEqual([]);
        expect(toastMock).not.toHaveBeenCalled();
    });

    it('edits choices of a choice question', async () => {
        await toReview();
        const choices = screen.getByLabelText(/Choices, one per line/);
        fireEvent.change(choices, { target: { value: 'Stalls\nCooking\nCleaning' } });
        buildMock.mockResolvedValue({ data: { formId: 'f', title: 't', quality: { score: 95, passed: true, findings: [{ code: 'x', severity: 'warning', message: 'm', where: [] }] }, notes: ['Suggested choices for 1 question(s).'] } });
        fireEvent.click(screen.getByRole('button', { name: /Build form/ }));
        await waitFor(() => expect(buildMock).toHaveBeenCalled());
        expect(buildMock.mock.calls[0][0].body.outline.pages[1].questions[0].choices).toEqual(['Stalls', 'Cooking', 'Cleaning']);
        // notes and findings are summed up for the person
        await waitFor(() => expect(toastMock).toHaveBeenCalled());
        expect(toastMock.mock.calls[0][0].description).toContain('1 thing to check before publishing.');
    });

    it('keeps the outline when the build fails, and says why', async () => {
        await toReview();
        buildMock.mockResolvedValue({ error: { status: 403, data: { code: 'ai_not_enabled', message: 'AI features are off for this workspace.' } } });
        fireEvent.click(screen.getByRole('button', { name: /Build form/ }));
        await screen.findByText('Review the outline');
        expect(toastMock).toHaveBeenCalledWith({ description: 'AI features are off for this workspace.', variant: 'destructive' });
        expect(replaceMock).not.toHaveBeenCalled();
    });

    it('goes back to the prompt and returns to the same outline', async () => {
        await toReview();
        fireEvent.change(screen.getByLabelText('Question 1'), { target: { value: 'Changed' } });
        fireEvent.click(screen.getByRole('button', { name: 'Back to prompt' }));
        expect(screen.getByRole('button', { name: /Draft a new outline/ })).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Back to the outline you were reviewing' }));
        expect(screen.getByLabelText('Question 1')).toHaveValue('Changed');
    });

    it('shows a failed outline request and stays on the prompt', async () => {
        outlineMock.mockResolvedValue({ error: { status: 502, data: { code: 'ai_unusable_reply', message: 'The AI returned an unusable outline.' } } });
        renderModal();
        fireEvent.change(screen.getByLabelText('Describe the form you need'), { target: { value: 'x' } });
        fireEvent.click(screen.getByRole('button', { name: /Draft outline/ }));
        await waitFor(() => expect(toastMock).toHaveBeenCalledWith({ description: 'The AI returned an unusable outline.', variant: 'destructive' }));
        expect(screen.getByLabelText('Describe the form you need')).toHaveValue('x');
    });
});

describe('OutlineReview list', () => {
    it('is a list of labelled controls per page', async () => {
        await toReview();
        const pages = screen.getAllByRole('region');
        expect(pages).toHaveLength(2);
        expect(within(pages[0]).getAllByRole('listitem')).toHaveLength(2);
        expect(within(pages[0]).getByRole('button', { name: 'Move What is your name? up' })).toBeDisabled();
    });
});
