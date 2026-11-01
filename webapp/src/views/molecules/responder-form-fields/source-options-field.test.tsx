// Respondent text resolves through the app's i18n instance.
import React from 'react';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import axe from 'axe-core';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import SourceOptionsField from './source-options-field';

// The options route: what it answers, and what it was asked, is the test's.
const route = vi.hoisted(() => ({ calls: [] as any[], answer: undefined as undefined | ((args: any) => Promise<any>) }));
vi.mock('@app/lib/source-options', async (importOriginal) => {
    const actual = await importOriginal<typeof import('@app/lib/source-options')>();
    return {
        ...actual,
        fetchSourceOptions: (args: any) => {
            route.calls.push(args);
            return route.answer ? route.answer(args) : Promise.reject(new Error('unavailable'));
        }
    };
});

vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ RenderImage: () => null, default: () => null }));

const CITIES = [
    { id: 'li1', label: 'Amsterdam' },
    { id: 'li2', label: 'Berlin' },
    { id: 'li3', label: 'Utrecht' }
];
const page = (items = CITIES, total = items.length) => Promise.resolve({ items, total, truncated: false, available: true });

const city: StandardFormFieldDto = { id: 'city', index: 1, type: FieldTypes.DROP_DOWN, title: 'City', properties: { optionSource: { kind: 'list' } } };
const many: StandardFormFieldDto = { id: 'cities', index: 2, type: FieldTypes.MULTIPLE_CHOICE, title: 'Cities', properties: { allowMultipleSelection: true, optionSource: { kind: 'form_answers' } } };
const dependent: StandardFormFieldDto = { id: 'town', index: 3, type: FieldTypes.DROP_DOWN, title: 'Town', properties: { optionSource: { kind: 'list', parentFieldId: 'country' } } };
const country: StandardFormFieldDto = {
    id: 'country',
    index: 0,
    type: FieldTypes.DROP_DOWN,
    title: 'Country',
    properties: {
        choices: [
            { id: 'nl', value: 'Netherlands' },
            { id: 'de', value: 'Germany' }
        ]
    }
};

let latest: Record<string, any> = {};
let setAnswers: (answers: Record<string, any>) => void = () => {};

function Spy() {
    const { formResponse, setFormResponse } = useFormResponse();
    latest = formResponse.answers ?? {};
    setAnswers = (answers) => setFormResponse({ ...formResponse, answers });
    return null;
}

const show = (field: StandardFormFieldDto, answers: Record<string, any> = {}) => {
    store.dispatch(setForm({ formId: 'form-1', title: 'Cities', fields: [{ id: 's1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [country, city, many, dependent] } }] }));
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'ws' }));
    const Harness = () => {
        const { setFormResponse, formResponse } = useFormResponse();
        const [ready, setReady] = React.useState(false);
        React.useEffect(() => {
            setFormResponse({ ...formResponse, answers });
            setReady(true);
        }, []);
        return ready ? <SourceOptionsField field={field} slideIndex={0} /> : null;
    };
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <Harness />
                <Spy />
            </Provider>
        </ReduxProvider>
    );
};

const open = async (name = 'City') => {
    fireEvent.click(await screen.findByRole('combobox', { name }));
    return screen.findByRole('listbox');
};

beforeEach(() => {
    route.calls = [];
    route.answer = () => page();
});
afterEach(() => {
    latest = {};
});

describe('SourceOptionsField', () => {
    it('is a combobox named by the question that opens a searchable list of labels', async () => {
        show(city);
        const trigger = await screen.findByRole('combobox', { name: 'City' });
        expect(trigger).toHaveAttribute('aria-expanded', 'false');
        const list = await open();
        expect(trigger).toHaveAttribute('aria-expanded', 'true');
        expect(
            within(list)
                .getAllByRole('option')
                .map((option) => option.textContent)
        ).toEqual(['Amsterdam', 'Berlin', 'Utrecht']);
        expect(screen.getByRole('status')).toHaveTextContent('3 choices');
        // the first request is the whole list's first page, with nothing from the browser but the question
        expect(route.calls[0]).toMatchObject({ workspaceId: 'ws-1', formId: 'form-1', fieldId: 'city', q: '', offset: 0, parent: [] });
    });

    it('chooses with the keyboard: arrows, Enter, and Escape back to the button', async () => {
        show(city);
        await open();
        await screen.findAllByRole('option');
        const search = screen.getByRole('combobox', { name: 'Search the choices' });
        fireEvent.keyDown(search, { key: 'ArrowDown' });
        expect(search).toHaveAttribute('aria-activedescendant', screen.getAllByRole('option')[1].id);
        fireEvent.keyDown(search, { key: 'Enter' });
        // the text goes with the id, so it shows (and is sent) before the server writes it again
        await waitFor(() => expect(latest.city).toEqual({ type: 'choice', choice: { value: 'li2', label: 'Berlin' } }));
        expect(screen.getByRole('combobox', { name: 'City' })).toHaveTextContent('Berlin');
        expect(screen.queryByRole('listbox')).toBeNull();
    });

    it('closes on Escape without choosing', async () => {
        show(city);
        await open();
        fireEvent.keyDown(screen.getByRole('combobox', { name: 'Search the choices' }), { key: 'Escape' });
        expect(screen.queryByRole('listbox')).toBeNull();
        expect(latest.city).toBeUndefined();
        expect(screen.getByRole('combobox', { name: 'City' })).toHaveFocus();
    });

    it('searches on the server, after a pause, with what was typed', async () => {
        show(city);
        await open();
        route.answer = ({ q }) =>
            page(
                CITIES.filter((c) => c.label.toLowerCase().includes(q)),
                1
            );
        fireEvent.change(screen.getByRole('combobox', { name: 'Search the choices' }), { target: { value: 'ber' } });
        await waitFor(() =>
            expect(
                within(screen.getByRole('listbox'))
                    .getAllByRole('option')
                    .map((o) => o.textContent)
            ).toEqual(['Berlin'])
        );
        expect(route.calls.some((call) => call.q === 'ber')).toBe(true);
    });

    it('says when nothing matches, and when the choices cannot be loaded', async () => {
        show(city);
        await open();
        route.answer = () => page([], 0);
        fireEvent.change(screen.getByRole('combobox', { name: 'Search the choices' }), { target: { value: 'zzz' } });
        expect(await screen.findByText('No choices match your search.')).toBeInTheDocument();
        route.answer = () => Promise.reject(new Error('down'));
        fireEvent.change(screen.getByRole('combobox', { name: 'Search the choices' }), { target: { value: 'q' } });
        expect(await screen.findByText('The choices could not be loaded. Try again.')).toBeInTheDocument();
    });

    it('loads the next page on request and does not repeat a choice', async () => {
        const first = Array.from({ length: 2 }, (_, i) => ({ id: `a${i}`, label: `Item ${i}` }));
        route.answer = ({ offset }) =>
            offset === 0
                ? page(first, 3)
                : page(
                      [
                          { id: 'a1', label: 'Item 1' },
                          { id: 'a2', label: 'Item 2' }
                      ],
                      3
                  );
        show(city);
        await open();
        fireEvent.click(await screen.findByRole('button', { name: 'Show more' }));
        await waitFor(() => expect(screen.getAllByRole('option')).toHaveLength(3));
        expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
    });

    it('chooses several and shows them as removable chips', async () => {
        show(many);
        await open('Cities');
        fireEvent.click(screen.getByRole('option', { name: 'Amsterdam' }));
        fireEvent.click(screen.getByRole('option', { name: 'Utrecht' }));
        await waitFor(() => expect(latest.cities.choices).toEqual({ values: ['li1', 'li3'], labels: { li1: 'Amsterdam', li3: 'Utrecht' } }));
        const chips = screen.getByRole('list', { name: 'Your choices' });
        expect(
            within(chips)
                .getAllByRole('listitem')
                .map((chip) => chip.textContent)
        ).toEqual(['Amsterdam', 'Utrecht']);
        fireEvent.click(within(chips).getByRole('button', { name: 'Remove Amsterdam' }));
        await waitFor(() => expect(latest.cities.choices.values).toEqual(['li3']));
        // the note for another form's answers is there, for everyone who answers
        expect(screen.getByText('The choices come from answers other people gave to another form of this organisation.')).toBeInTheDocument();
    });

    it('asks for a dependent list with the ids chosen in its parent, and clears its answer when the parent changes', async () => {
        show(dependent, { country: { type: 'choice', choice: { value: 'nl' } }, town: { type: 'choice', choice: { value: 'li1', label: 'Amsterdam' } } });
        await screen.findByRole('combobox', { name: 'Town' });
        await waitFor(() => expect(route.calls.some((call) => call.fieldId === 'town' && call.parent?.[0] === 'nl')).toBe(true));
        act(() => setAnswers({ country: { type: 'choice', choice: { value: 'de' } }, town: latest.town }));
        await waitFor(() => expect(latest.town).toBeUndefined());
        expect(await screen.findByText(/Your choice was removed because it depends on an answer you changed/)).toBeInTheDocument();
    });

    it('is a valid, labelled control (axe)', async () => {
        const { container } = show(city);
        await open();
        const results = await axe.run(container, { rules: { region: { enabled: false } } });
        expect(results.violations.map((violation) => violation.id)).toEqual([]);
    });
});
