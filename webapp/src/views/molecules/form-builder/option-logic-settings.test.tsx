import React from 'react';

import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider, createStore } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { activeFieldAtom, activeSlideAtom } from '@app/store/jotai/active-builder-component';
import { builderFieldsAtom, resetFromServerAtom } from '@app/store/jotai/form-document';
import { axeViolations } from '@app/test/axe';

import OptionLogicSettings from './option-logic-settings';

// The server's answer (with the permissions): whether it takes choice logic.
const served = vi.hoisted(() => ({ choiceLogicEnabled: true }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ choiceLogicEnabled: served.choiceLogicEnabled }) }));

const choices = (...pairs: Array<[string, string]>) => pairs.map(([id, value]) => ({ id, value }));
const question = (id: string, index: number, type: FieldTypes, title: string, properties: StandardFormFieldDto['properties'] = {}, extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({
    id,
    index,
    type,
    title,
    properties: { fields: [], ...properties },
    ...extra
});

const form = (fields: StandardFormFieldDto[]) => ({ formId: 'form-1', title: 'Form', fields: [{ id: 'page-1', index: 0, type: FieldTypes.SLIDE, properties: { fields } }] });

const COUNTRY = question('country', 0, FieldTypes.DROP_DOWN, 'Country', { choices: choices(['nl', 'Netherlands'], ['de', 'Germany'], ['be', 'Belgium']) });
const CITY = question('city', 1, FieldTypes.MULTIPLE_CHOICE, 'City', { choices: choices(['ams', 'Amsterdam'], ['ber', 'Berlin'], ['bru', 'Brussels']) });

function setup(fields: StandardFormFieldDto[], activeId: string) {
    const jotai = createStore();
    jotai.set(resetFromServerAtom, form(fields) as any);
    jotai.set(activeSlideAtom, { id: 'page-1', index: 0 });
    jotai.set(activeFieldAtom, { id: activeId, index: fields.findIndex((field) => field.id === activeId) });
    const view = render(
        <Provider store={jotai}>
            <OptionLogicSettings />
        </Provider>
    );
    const fieldNow = (id: string) => jotai.get(builderFieldsAtom)[0].properties!.fields!.find((field) => field.id === id)!;
    return { jotai, view, fieldNow };
}

describe('option logic in the builder', () => {
    beforeEach(() => {
        served.choiceLogicEnabled = true;
        i18n.changeLanguage('en');
    });
    afterEach(cleanup);

    it('shows nothing for a question that is not a choice question', () => {
        setup([COUNTRY, question('name', 1, FieldTypes.SHORT_TEXT, 'Name')], 'name');
        expect(screen.queryByTestId('option-logic-settings')).not.toBeInTheDocument();
    });

    it('says an earlier question is needed when the choice question comes first', () => {
        setup([question('first', 0, FieldTypes.DROP_DOWN, 'First', { choices: choices(['a', 'A'], ['b', 'B']) })], 'first');
        expect(screen.getByText('Add a question before this one to show or hide its options based on an earlier answer.')).toBeInTheDocument();
        // the filter switch is off and cannot be turned on: nothing earlier to filter by
        expect(screen.getByRole('switch', { name: 'Filter options by an earlier answer' })).toBeDisabled();
    });

    it('gives an option its own "show this option when…" with the existing condition builder', async () => {
        const { fieldNow } = setup([COUNTRY, CITY], 'city');
        await act(async () => fireEvent.click(screen.getByRole('switch', { name: 'Show or hide the option “Berlin” based on answers' })));
        const logic = fieldNow('city').properties!.choices![1].logic!;
        expect(logic).toMatchObject({ action: 'SHOW', operator: 'AND', conditions: [{ fieldId: 'country', fieldType: 'dropdown', comparison: 'IS_EQUAL' }] });
        // the other options are untouched
        expect(fieldNow('city').properties!.choices![0].logic).toBeUndefined();
        // "Hide this option when…"
        const berlin = screen.getByRole('group', { name: 'Berlin' });
        await act(async () => fireEvent.change(within(berlin).getByRole('combobox', { name: 'Berlin' }), { target: { value: 'HIDE' } }));
        expect(fieldNow('city').properties!.choices![1].logic!.action).toBe('HIDE');
        // turning it off removes the key altogether
        await act(async () => fireEvent.click(screen.getByRole('switch', { name: 'Show or hide the option “Berlin” based on answers' })));
        expect('logic' in fieldNow('city').properties!.choices![1]).toBe(false);
    });

    it('filters by an earlier choice question with a table, one checkbox for each pair', async () => {
        const { fieldNow } = setup([COUNTRY, CITY], 'city');
        await act(async () => fireEvent.click(screen.getByRole('switch', { name: 'Filter options by an earlier answer' })));
        const filter = fieldNow('city').properties!.optionFilter!;
        expect(filter.fieldId).toBe('country');
        // every option offered for every answer to start with: nothing is lost until it is unticked
        expect(filter.mapping).toEqual([
            { when: 'nl', show: ['ams', 'ber', 'bru'] },
            { when: 'de', show: ['ams', 'ber', 'bru'] },
            { when: 'be', show: ['ams', 'ber', 'bru'] }
        ]);
        const table = screen.getByRole('table', { name: 'Options of “City” to offer for each answer to “Country”' });
        // read with its row and its column
        expect(within(table).getByRole('rowheader', { name: 'Berlin' })).toBeInTheDocument();
        expect(within(table).getByRole('columnheader', { name: 'Germany' })).toBeInTheDocument();
        expect(screen.queryByTestId('option-logic-warnings')).not.toBeInTheDocument();

        await act(async () => fireEvent.click(screen.getByRole('checkbox', { name: 'Offer “Amsterdam” when “Country” is “Germany”' })));
        expect(fieldNow('city').properties!.optionFilter!.mapping.find((entry) => entry.when === 'de')!.show).toEqual(['ber', 'bru']);
        // untick everything for one answer: the shared check warns in words
        await act(async () => {
            fireEvent.click(screen.getByRole('checkbox', { name: 'Offer “Berlin” when “Country” is “Belgium”' }));
            fireEvent.click(screen.getByRole('checkbox', { name: 'Offer “Brussels” when “Country” is “Belgium”' }));
            fireEvent.click(screen.getByRole('checkbox', { name: 'Offer “Amsterdam” when “Country” is “Belgium”' }));
        });
        const note = screen.getByRole('note', { name: 'Check these' });
        expect(note.textContent).toContain('Choosing “Belgium” in “Country” leaves no option to choose here.');
        // turning the filter off removes it
        await act(async () => fireEvent.click(screen.getByRole('switch', { name: 'Filter options by an earlier answer' })));
        expect(fieldNow('city').properties!.optionFilter).toBeUndefined();
    });

    it('warns about an option no row shows', async () => {
        const filtered = {
            ...CITY,
            properties: {
                ...CITY.properties,
                optionFilter: {
                    fieldId: 'country',
                    mapping: [
                        { when: 'nl', show: ['ams'] },
                        { when: 'de', show: ['ber'] },
                        { when: 'be', show: ['ams'] }
                    ]
                }
            }
        };
        setup([COUNTRY, filtered], 'city');
        expect(screen.getByRole('note', { name: 'Check these' }).textContent).toContain('“Brussels” is never offered: no answer to “Country” shows it.');
    });

    it('speaks Dutch with the builder language', () => {
        i18n.changeLanguage('nl');
        setup([COUNTRY, CITY], 'city');
        expect(screen.getByText('Opties')).toBeInTheDocument();
        expect(screen.getByRole('switch', { name: 'Opties filteren op een eerder antwoord' })).toBeInTheDocument();
        expect(screen.getByRole('switch', { name: 'De optie “Berlin” tonen of verbergen op basis van antwoorden' })).toBeInTheDocument();
    });

    it('has no automated accessibility violations, with logic and a filter in place', async () => {
        const logicChoice = { id: 'ber', value: 'Berlin', logic: { action: 'SHOW' as const, operator: 'AND' as any, conditions: [{ fieldId: 'country', fieldType: 'dropdown', comparison: 'IS_EQUAL' as any, value: 'Germany' }] } };
        const city = {
            ...CITY,
            properties: {
                ...CITY.properties,
                choices: [CITY.properties!.choices![0], logicChoice, CITY.properties!.choices![2]],
                optionFilter: {
                    fieldId: 'country',
                    mapping: [
                        { when: 'nl', show: ['ams'] },
                        { when: 'de', show: ['ber'] }
                    ]
                }
            }
        };
        const { view } = setup([COUNTRY, city], 'city');
        expect(await axeViolations(view.container)).toEqual([]);
    });

    describe('with choice logic switched off on the server', () => {
        beforeEach(() => {
            served.choiceLogicEnabled = false;
        });

        it('shows nothing on a question that has no option logic', () => {
            setup([COUNTRY, CITY], 'city');
            expect(screen.queryByTestId('option-logic-settings')).not.toBeInTheDocument();
        });

        it('lists what a question already has, read-only, and says it is still applied', () => {
            const logicChoice = { id: 'ber', value: 'Berlin', logic: { action: 'SHOW' as const, operator: 'AND' as any, conditions: [{ fieldId: 'country', fieldType: 'dropdown', comparison: 'IS_EQUAL' as any, value: 'Germany' }] } };
            const city = {
                ...CITY,
                properties: {
                    ...CITY.properties,
                    choices: [CITY.properties!.choices![0], logicChoice, CITY.properties!.choices![2]],
                    optionFilter: {
                        fieldId: 'country',
                        mapping: [
                            { when: 'nl', show: ['ams'] },
                            { when: 'de', show: ['ber'] },
                            { when: 'be', show: ['bru'] }
                        ]
                    }
                }
            };
            setup([COUNTRY, city], 'city');
            expect(screen.getByTestId('option-logic-disabled').textContent).toContain('cannot be created or changed on this server yet');
            // every control is disabled: nothing can be edited
            const group = screen.getByTestId('option-logic-settings').querySelector('fieldset')!;
            expect(group.disabled).toBe(true);
            expect(screen.getByRole('switch', { name: 'Filter options by an earlier answer' })).toBeDisabled();
            expect(screen.getByRole('switch', { name: 'Show or hide the option “Berlin” based on answers' })).toBeDisabled();
            expect(screen.getByRole('table')).toBeInTheDocument();
        });
    });

    it('warns about a question with more options than option logic may sit on', () => {
        const many = Array.from({ length: 201 }, (_, i) => ({ id: `o${i}`, value: `City ${i}` }));
        const city = { ...CITY, properties: { ...CITY.properties, choices: many, optionFilter: { fieldId: 'country', mapping: [{ when: 'nl', show: ['o0'] }] } } };
        setup([COUNTRY, city], 'city');
        expect(screen.getByRole('note', { name: 'Check these' }).textContent).toContain('more than 200 options');
    });
});
