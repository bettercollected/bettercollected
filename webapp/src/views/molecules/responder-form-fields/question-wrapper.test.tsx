import React from 'react';

import { render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, describe, expect, it, vi } from 'vitest';

// RenderImage drags in the whole builder field registry — irrelevant here.
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { store } from '@app/store/store';
import QuestionWrapper from './question-wrapper';
// Registers the respondent translations, as the app layout does.
import '@app/shared/hocs/i18n-provider';

const field = (overrides: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({ id: 'f1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Your name?', ...overrides });

/** Renders QuestionWrapper with optional pre-seeded invalid fields / answers / hidden values. */
const renderWrapper = (f: StandardFormFieldDto, opts: { invalid?: Record<string, any[]>; answers?: Record<string, any>; hiddenValues?: Record<string, string> } = {}) => {
    const { invalid, answers, hiddenValues } = opts;
    const needsSetup = !!(invalid || answers || hiddenValues);
    const Harness = () => {
        const { setInvalidFields, setFormResponse, formResponse } = useFormResponse();
        const { setHiddenValues } = useHiddenFieldValues();
        const [ready, setReady] = React.useState(!needsSetup);
        React.useEffect(() => {
            if (!needsSetup) return;
            if (invalid) setInvalidFields(invalid as any);
            if (answers) setFormResponse({ ...formResponse, answers });
            if (hiddenValues) setHiddenValues(hiddenValues);
            setReady(true);
            // eslint-disable-next-line react-hooks/exhaustive-deps
        }, []);
        return ready ? <QuestionWrapper field={f} /> : null;
    };
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <Harness />
            </Provider>
        </ReduxProvider>
    );
};

describe('QuestionWrapper — no-dark-patterns contracts (Design-Language §5)', () => {
    it('marks optional answerable fields explicitly — optionality is never hidden', () => {
        renderWrapper(field());
        expect(screen.getByText('Optional')).toBeInTheDocument();
    });

    it('does not mark required fields as optional', () => {
        renderWrapper(field({ validations: { required: true } }));
        expect(screen.queryByText('Optional')).not.toBeInTheDocument();
    });

    it('display-only fields (statements) carry no optional marker', () => {
        renderWrapper(field({ type: FieldTypes.TEXT }));
        expect(screen.queryByText('Optional')).not.toBeInTheDocument();
    });

    it('renders the question title', () => {
        renderWrapper(field());
        expect(screen.getByText('Your name?')).toBeInTheDocument();
    });

    it('shows calm, instructive validation copy when the field is invalid', () => {
        renderWrapper(field({ validations: { required: true } }), { invalid: { f1: [0] } });
        expect(screen.getByText('Please answer this question to continue.')).toBeInTheDocument();
    });

    it('shows no validation message when the field is valid', () => {
        renderWrapper(field());
        expect(screen.queryByText(/Please answer/)).not.toBeInTheDocument();
    });
});

describe('QuestionWrapper — answer piping', () => {
    it('resolves hidden-field pipes in the title', () => {
        const title = {
            type: 'doc',
            content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Hi ' }, { type: 'answerPipe', attrs: { kind: 'hidden', pipeKey: 'name', label: 'name', fallback: 'there' } }] }]
        };
        renderWrapper(field({ title }), { hiddenValues: { name: 'Ada' } });
        expect(screen.getByText(/Hi Ada/)).toBeInTheDocument();
    });

    it('falls back when the pipe has no value yet', () => {
        const title = {
            type: 'doc',
            content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Hi ' }, { type: 'answerPipe', attrs: { kind: 'hidden', pipeKey: 'name', label: 'name', fallback: 'there' } }] }]
        };
        renderWrapper(field({ title }));
        expect(screen.getByText(/Hi there/)).toBeInTheDocument();
    });

    it('resolves text tokens in the description', () => {
        renderWrapper(field({ description: 'You came from {{hidden:utm_source|somewhere}}.' }), { hiddenValues: { utm_source: 'newsletter' } });
        expect(screen.getByText('You came from newsletter.')).toBeInTheDocument();
    });
});

describe('QuestionWrapper — string titles are text, never markup', () => {
    it('renders markup in a string title literally', () => {
        const { container } = renderWrapper(field({ title: 'Applicants <iframe srcdoc="<script>alert(1)</script>"></iframe>' }));
        expect(container.querySelector('iframe')).toBeNull();
        expect(screen.getByText(/Applicants <iframe srcdoc=/)).toBeInTheDocument();
    });

    it('renders a piped value in a string title as text', () => {
        const { container } = renderWrapper(field({ title: 'Hello {{hidden:name}}!' }), { hiddenValues: { name: '<img src=x onerror="alert(1)">' } });
        expect(container.querySelector('img')).toBeNull();
        expect(screen.getByText('Hello <img src=x onerror="alert(1)">!')).toBeInTheDocument();
    });

    it('keeps plain string titles bold', () => {
        const { container } = renderWrapper(field({ title: 'Your name?' }));
        expect(container.querySelector('strong')?.textContent).toBe('Your name?');
    });
});

describe('QuestionWrapper — "why we ask this"', () => {
    afterEach(() => vi.restoreAllMocks());

    it('shows the reason under an identifying question and links it for assistive tech (English)', async () => {
        vi.spyOn(window.navigator, 'languages', 'get').mockReturnValue(['en-GB']);
        renderWrapper(field({ type: FieldTypes.EMAIL, title: 'Email', properties: { whyWeAsk: 'To send you a copy of your answers.' } }));
        const reason = await screen.findByText(/To send you a copy of your answers\./);
        expect(reason.closest('p')).toHaveTextContent('Why we ask this: To send you a copy of your answers.');
        expect(screen.getByRole('group').getAttribute('aria-describedby')).toContain('q-why-f1');
    });

    it('labels the reason in Dutch for a Dutch respondent', async () => {
        vi.spyOn(window.navigator, 'languages', 'get').mockReturnValue(['nl-NL']);
        renderWrapper(field({ type: FieldTypes.PHONE_NUMBER, title: 'Telefoon', properties: { whyWeAsk: 'Zodat we je kunnen terugbellen.' } }));
        const reason = await screen.findByText(/Zodat we je kunnen terugbellen\./);
        await waitFor(() => expect(reason.closest('p')).toHaveTextContent('Waarom we dit vragen: Zodat we je kunnen terugbellen.'));
    });

    it('shows nothing without a reason', () => {
        renderWrapper(field({ type: FieldTypes.EMAIL, title: 'Email' }));
        expect(screen.queryByText(/why we ask this/i)).not.toBeInTheDocument();
    });
});
