import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { describe, expect, it, vi } from 'vitest';

// RenderImage drags in the whole builder field registry — irrelevant here.
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import QuestionWrapper from './question-wrapper';

const field = (overrides: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({ id: 'f1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Your name?', ...overrides });

/** Renders QuestionWrapper with optional pre-seeded invalid fields. */
const renderWrapper = (f: StandardFormFieldDto, invalid?: Record<string, any[]>) => {
    const Harness = () => {
        const { setInvalidFields } = useFormResponse();
        const [ready, setReady] = React.useState(!invalid);
        React.useEffect(() => {
            if (invalid) {
                setInvalidFields(invalid as any);
                setReady(true);
            }
            // eslint-disable-next-line react-hooks/exhaustive-deps
        }, []);
        return ready ? <QuestionWrapper field={f} /> : null;
    };
    return render(
        <Provider>
            <Harness />
        </Provider>
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
        renderWrapper(field({ validations: { required: true } }), { f1: [0] });
        expect(screen.getByText('Please answer this question to continue.')).toBeInTheDocument();
    });

    it('shows no validation message when the field is valid', () => {
        renderWrapper(field());
        expect(screen.queryByText(/Please answer/)).not.toBeInTheDocument();
    });
});
