// Question numbers on the respondent page when the form has numbering on
// (outside the Leaflet style, which always numbers).
import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';

import FormSlide from './form-slide';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const field = (id: string, type: FieldTypes, validations: StandardFormFieldDto['validations'], properties: StandardFormFieldDto['properties'] = {}): StandardFormFieldDto => ({ id, index: 0, type, title: `Question ${id}`, validations, properties });
const slide = (id: string, index: number, fields: StandardFormFieldDto[], properties: StandardFormFieldDto['properties'] = {}): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, properties: { fields, ...properties } });

function Page() {
    return <FormSlide index={0} isPreviewMode />;
}

const open = (fields: StandardFormFieldDto[], pageProperties: StandardFormFieldDto['properties'] = {}, pages = 2) => {
    store.dispatch(
        setForm({
            formId: `numbers-${Math.random()}`,
            title: 'Numbers',
            fields: [slide('s1', 0, fields, pageProperties), ...Array.from({ length: pages - 1 }, (_, i) => slide(`s${i + 2}`, i + 1, []))]
        })
    );
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <Page />
            </Provider>
        </ReduxProvider>
    );
};

describe('question numbers on the respondent page', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
    });

    const questions = [field('q1', FieldTypes.SHORT_TEXT, {}), { ...field('t', FieldTypes.TEXT, {}), index: 1 }, { ...field('q2', FieldTypes.SHORT_TEXT, {}), index: 2 }];

    it('numbered by page when the form has numbering on (statements are not numbered)', async () => {
        open(questions, { showQuestionNumbers: true });
        await screen.findByRole('button', { name: 'Continue' });
        expect(screen.getAllByTestId('question-number').map((n) => n.textContent)).toEqual(['1.1', '1.2']);
    });

    it('1., 2., … on a one-page form', async () => {
        open(questions, { showQuestionNumbers: true }, 1);
        await screen.findByText('Question q1');
        expect(screen.getAllByTestId('question-number').map((n) => n.textContent)).toEqual(['1.', '2.']);
    });

    it('no numbers when numbering is off', async () => {
        open(questions);
        await screen.findByRole('button', { name: 'Continue' });
        expect(screen.queryAllByTestId('question-number')).toHaveLength(0);
    });
});
