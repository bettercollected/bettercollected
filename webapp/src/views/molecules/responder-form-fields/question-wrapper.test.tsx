import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

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
