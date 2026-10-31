import React from 'react';

import { render, screen, within } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it } from 'vitest';

import { FieldTypes } from '@app/models/dtos/form';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';

import ReadOnlyForm from './read-only-form';

const field = (id: string, index: number, type: FieldTypes, title: string, properties: Record<string, any> = {}) => ({ id, index, type, title, properties });
const form = (language?: string) =>
    ({
        formId: 'f',
        title: 'Typed answers',
        builderVersion: 'v2',
        version: 1,
        settings: { provider: 'self', ...(language ? { language } : {}) },
        fields: [
            {
                id: 'p1',
                index: 0,
                type: FieldTypes.SLIDE,
                properties: {
                    fields: [
                        field('arrival', 0, FieldTypes.TIME, 'When do you arrive?'),
                        field('born', 1, FieldTypes.DAY, 'When were you born?'),
                        field('budget', 2, FieldTypes.CURRENCY, 'What is your budget?', { currencies: ['EUR', 'GBP'] }),
                        field('spare', 3, FieldTypes.CURRENCY, 'Anything spare?')
                    ]
                }
            }
        ]
    }) as any;

const response = (answers: Record<string, any>) => ({ responseId: 'r', createdAt: '2026-10-01T10:00:00Z', answers }) as any;
const ANSWERS = {
    arrival: { field: { id: 'arrival' }, type: 'time', time: '09:05' },
    born: { field: { id: 'born' }, type: 'date', date: '1990-11-05' },
    budget: { field: { id: 'budget' }, type: 'currency', currency: { code: 'GBP', amount: '1250.5' } }
};

const show = (language?: string, answers: Record<string, any> = ANSWERS) =>
    render(
        <ReduxProvider store={store}>
            <ReadOnlyForm form={form(language)} response={response(answers)} />
        </ReduxProvider>
    );

const box = (title: string | RegExp) => within(screen.getAllByRole('group', { name: title })[0]).getByRole('textbox');

beforeEach(() => {
    store.dispatch(setWorkspace({ id: 'workspace-1', workspaceName: 'acme' } as any));
});

describe('time, day and currency answers on the response page', () => {
    it('show the time, the day as the form writes dates and the amount with its currency', () => {
        show();
        expect(box(/When do you arrive\?/)).toHaveTextContent('09:05');
        expect(box(/When were you born\?/)).toHaveTextContent('November 5th, 1990');
        expect(box(/What is your budget\?/).textContent?.replace(/\s/g, ' ')).toBe('£1,250.50');
    });

    it('write the day and the amount the Dutch way in a Dutch form', () => {
        show('nl');
        expect(box(/When were you born\?/)).toHaveTextContent('5 november 1990');
        expect(box(/What is your budget\?/).textContent?.replace(/\s/g, ' ')).toBe('£ 1.250,50');
    });

    it('say there is no answer for what was left empty', () => {
        show(undefined, {});
        expect(screen.getAllByText(/No answer/i).length).toBeGreaterThanOrEqual(4);
    });

    it('are read-only boxes with no violations', async () => {
        const { container } = show();
        expect(box(/When do you arrive\?/)).toHaveAttribute('aria-readonly', 'true');
        expect(await axeViolations(container)).toEqual([]);
    });
});
