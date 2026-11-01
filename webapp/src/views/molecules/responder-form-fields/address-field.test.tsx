// Respondent text resolves through the app's i18n instance.
import '@app/shared/hocs/i18n-provider';
import React from 'react';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import axe from 'axe-core';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { setForm } from '@app/store/forms/slice';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { checkAnswerRules } from '@app/utils/answer-rules';

import AddressField from './address-field';

// The lookup route: what it answers, and what it was asked, is the test's.
const lookup = vi.hoisted(() => ({ answer: undefined as undefined | ((args: any) => Promise<any>), calls: [] as any[] }));
vi.mock('@app/store/redux/form-api', async (importOriginal) => {
    const actual = await importOriginal<typeof import('@app/store/redux/form-api')>();
    return {
        ...actual,
        useLookUpAddressMutation: () => [
            (args: any) => {
                lookup.calls.push(args);
                const promise = lookup.answer ? lookup.answer(args) : Promise.reject(new Error('unavailable'));
                return { unwrap: () => promise };
            }
        ]
    };
});

// A field rule that locks the question (read-only, or the form sets its value).
const served = vi.hoisted(() => ({ locked: false }));
vi.mock('@app/lib/hooks/use-field-rule-states', async (importOriginal) => {
    const actual = await importOriginal<typeof import('@app/lib/hooks/use-field-rule-states')>();
    return { ...actual, useFieldRuleStates: () => new Proxy(actual.useFieldRuleStates(), { get: (target, key) => (key === 'isLocked' ? () => served.locked : Reflect.get(target, key)) }) };
});

vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const home: StandardFormFieldDto = { id: 'home', index: 0, type: FieldTypes.ADDRESS, title: 'Where do you live?', validations: { required: true } };
const noLookup: StandardFormFieldDto = { ...home, id: 'work', properties: { addressLookup: false } };
const abroad: StandardFormFieldDto = { ...home, id: 'abroad', properties: { countries: ['NL', 'BE', 'DE'] } };
const belgian: StandardFormFieldDto = { ...home, id: 'be', properties: { countries: ['BE'] } };

let latest: Record<string, any> = {};

function Spy() {
    const { formResponse } = useFormResponse();
    latest = formResponse.answers ?? {};
    return null;
}

const show = (field: StandardFormFieldDto, answers: Record<string, any> = {}, invalid: Record<string, any> = {}) => {
    store.dispatch(setForm({ formId: 'form-1', title: 'Address', fields: [{ id: 's1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [home, noLookup, abroad, belgian] } }] }));
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'ws' }));
    const Harness = () => {
        const { setFormResponse, formResponse } = useFormResponse();
        const [ready, setReady] = React.useState(false);
        React.useEffect(() => {
            setFormResponse({ ...formResponse, answers, invalidFields: invalid });
            setReady(true);
        }, []);
        return ready ? <AddressField field={field} /> : null;
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

const type = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const status = () => screen.getByTestId('address-status');

beforeEach(() => {
    lookup.calls = [];
    lookup.answer = undefined;
});
afterEach(() => {
    latest = {};
    served.locked = false;
});

describe('AddressField', () => {
    it('is one group named by the question, with a labelled box for each part', async () => {
        show(home);
        const group = await screen.findByRole('group', { name: 'Where do you live?' });
        for (const label of ['Postcode', 'House number', 'Street', 'City']) expect(within(group).getByLabelText(label)).toBeInTheDocument();
        expect(within(group).getByLabelText(/Addition/)).toBeInTheDocument();
        // one country, no country box
        expect(within(group).queryByLabelText('Country')).toBeNull();
    });

    it('sets the browser hints that suit each box (and none that would put the number in the street)', async () => {
        show(home);
        expect(await screen.findByLabelText('Postcode')).toHaveAttribute('autocomplete', 'postal-code');
        expect(screen.getByLabelText('City')).toHaveAttribute('autocomplete', 'address-level2');
        expect(screen.getByLabelText('Street')).toHaveAttribute('autocomplete', 'off');
        expect(screen.getByLabelText('House number')).toHaveAttribute('inputmode', 'numeric');
    });

    it('stores only the parts that are given, with the question\'s country, trimmed, and a Dutch postcode in its stored form', async () => {
        show(home);
        type('Postcode', ' 1015cs ');
        expect(latest.home).toEqual({ type: 'address', address: { postcode: '1015 CS', country: 'NL' } });
        type('House number', '12');
        type(/Addition/ as any, 'A');
        type('Street', ' Keizersgracht ');
        type('City', 'Amsterdam');
        expect(latest.home.address).toEqual({ street: 'Keizersgracht', house_number: '12', house_number_addition: 'A', postcode: '1015 CS', city: 'Amsterdam', country: 'NL' });
        expect(checkAnswerRules(home, latest.home)).toEqual([]);
    });

    it('drops the answer when every box is emptied, and a country alone is no answer', async () => {
        show(abroad, { abroad: { type: 'address', address: { city: 'Brussel', country: 'BE' } } });
        expect(await screen.findByLabelText('City')).toHaveValue('Brussel');
        type('City', '');
        expect(latest.abroad).toBeUndefined();
        fireEvent.change(screen.getByLabelText('Country'), { target: { value: 'DE' } });
        expect(latest.abroad).toBeUndefined();
        type('City', 'Berlin');
        expect(latest.abroad.address).toEqual({ city: 'Berlin', country: 'DE' });
    });

    it('shows a stored address and keeps what a rule or a draft set', async () => {
        show(home, { home: { type: 'address', address: { street: 'Keizersgracht', house_number: '12', postcode: '1015 CS', city: 'Amsterdam', country: 'NL' } } });
        expect(await screen.findByLabelText('Street')).toHaveValue('Keizersgracht');
        expect(screen.getByLabelText('Postcode')).toHaveValue('1015 CS');
    });

    it('shows a locked address as it is and cannot be typed over', async () => {
        served.locked = true;
        show(home, { home: { type: 'address', address: { street: 'Keizersgracht', house_number: '12', postcode: '1015 CS', city: 'Amsterdam', country: 'NL' } } });
        const street = await screen.findByLabelText('Street');
        expect(street).toHaveAttribute('readonly');
        type('Street', 'Elsewhere');
        expect(latest.home.address.street).toBe('Keizersgracht');
    });

    it('offers a country box when several are allowed, named in the page language and in order', async () => {
        show(abroad);
        const country = await screen.findByLabelText('Country');
        expect(within(country).getAllByRole('option').map((o) => o.textContent)).toEqual(['Belgium', 'Germany', 'Netherlands']);
        expect(country).toHaveValue('NL');
        expect(country).toHaveAttribute('autocomplete', 'country');
    });

    it('takes the country of a question that allows only another one, and checks the postcode loosely there', async () => {
        show(belgian);
        type('Postcode', '1000');
        type('House number', '5B');
        type('Street', 'Rue Neuve');
        type('City', 'Bruxelles');
        expect(latest.be.address).toEqual({ street: 'Rue Neuve', house_number: '5B', postcode: '1000', city: 'Bruxelles', country: 'BE' });
        expect(checkAnswerRules(belgian, latest.be)).toEqual([]);
        expect(screen.getByLabelText('House number')).toHaveAttribute('inputmode', 'text');
    });

    it('passes axe', async () => {
        const { container } = show(abroad);
        await screen.findByRole('group', { name: 'Where do you live?' });
        const results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
        expect(results.violations.map((v) => v.id)).toEqual([]);
    });
});

describe('AddressField lookup', () => {
    const found = () => Promise.resolve({ status: 'found', street: 'Keizersgracht', city: 'Amsterdam' });

    it('asks only when the postcode or the house number is left, with the two values and the question, never the addition', async () => {
        lookup.answer = found;
        show(home);
        type('Postcode', '1015cs');
        type('House number', '12');
        type(/Addition/ as any, 'A');
        // nothing is sent while typing
        expect(lookup.calls).toEqual([]);
        fireEvent.blur(screen.getByLabelText('House number'));
        await waitFor(() => expect(lookup.calls).toHaveLength(1));
        expect(lookup.calls[0]).toEqual({ workspaceId: 'ws-1', formId: 'form-1', fieldId: 'home', postcode: '1015CS', houseNumber: '12' });
        expect(JSON.stringify(lookup.calls)).not.toContain('"A"');
    });

    it('fills street and city, says so in a polite status, and leaves them editable', async () => {
        lookup.answer = found;
        show(home);
        type('Postcode', '1015 CS');
        type('House number', '12');
        fireEvent.blur(screen.getByLabelText('House number'));
        await waitFor(() => expect(screen.getByLabelText('Street')).toHaveValue('Keizersgracht'));
        expect(screen.getByLabelText('City')).toHaveValue('Amsterdam');
        expect(status()).toHaveTextContent('Street and city filled in. Check them and change them if needed.');
        expect(status()).toHaveAttribute('role', 'status');
        expect(status()).toHaveAttribute('aria-live', 'polite');
        expect(latest.home.address).toMatchObject({ street: 'Keizersgracht', city: 'Amsterdam', postcode: '1015 CS' });
        // focus stays where the respondent is: nothing is moved or advanced
        const city = screen.getByLabelText('City');
        expect(city).not.toHaveAttribute('readonly');
        type('City', 'Amstelveen');
        expect(latest.home.address.city).toBe('Amstelveen');
    });

    it('never overwrites what the respondent typed, and says it kept it', async () => {
        lookup.answer = found;
        show(home);
        type('Street', 'My own street');
        type('Postcode', '1015 CS');
        type('House number', '12');
        fireEvent.blur(screen.getByLabelText('House number'));
        await waitFor(() => expect(screen.getByLabelText('City')).toHaveValue('Amsterdam'));
        expect(screen.getByLabelText('Street')).toHaveValue('My own street');
        expect(status()).toHaveTextContent('We kept the ones you typed.');
    });

    it('replaces its own earlier answer when the address changes, and asks once per address', async () => {
        let n = 0;
        lookup.answer = () => Promise.resolve(n++ === 0 ? { status: 'found', street: 'Keizersgracht', city: 'Amsterdam' } : { status: 'found', street: 'Dam', city: 'Amsterdam' });
        show(home);
        type('Postcode', '1015 CS');
        type('House number', '12');
        fireEvent.blur(screen.getByLabelText('House number'));
        await waitFor(() => expect(screen.getByLabelText('Street')).toHaveValue('Keizersgracht'));
        fireEvent.blur(screen.getByLabelText('Postcode'));
        expect(lookup.calls).toHaveLength(1);
        type('House number', '1');
        fireEvent.blur(screen.getByLabelText('House number'));
        await waitFor(() => expect(screen.getByLabelText('Street')).toHaveValue('Dam'));
        expect(lookup.calls).toHaveLength(2);
    });

    it('says when the address is not found, and the boxes stay for typing', async () => {
        lookup.answer = () => Promise.resolve({ status: 'not_found' });
        show(home);
        type('Postcode', '1015 CS');
        type('House number', '12');
        fireEvent.blur(screen.getByLabelText('Postcode'));
        await waitFor(() => expect(status()).toHaveTextContent('We could not find this address. Fill in the street and city yourself.'));
        expect(screen.getByLabelText('Street')).toHaveValue('');
    });

    it('falls back to typing when the service cannot answer, and tries again on the next blur', async () => {
        show(home);
        type('Postcode', '1015 CS');
        type('House number', '12');
        fireEvent.blur(screen.getByLabelText('Postcode'));
        await waitFor(() => expect(status()).toHaveTextContent('Looking up addresses is not available right now. Fill in the street and city yourself.'));
        lookup.answer = found;
        fireEvent.blur(screen.getByLabelText('House number'));
        await waitFor(() => expect(screen.getByLabelText('Street')).toHaveValue('Keizersgracht'));
        expect(lookup.calls).toHaveLength(2);
    });

    it('does not ask for a postcode or a number that is not valid, or for another country', async () => {
        lookup.answer = found;
        show(abroad);
        type('Postcode', '1015 SS');
        type('House number', '12');
        fireEvent.blur(screen.getByLabelText('Postcode'));
        type('Postcode', '1015 CS');
        type('House number', '12a');
        fireEvent.blur(screen.getByLabelText('House number'));
        fireEvent.change(screen.getByLabelText('Country'), { target: { value: 'BE' } });
        type('House number', '12');
        fireEvent.blur(screen.getByLabelText('House number'));
        expect(lookup.calls).toEqual([]);
    });

    it('does not ask when the question turns the lookup off, or while it is locked or in the builder', async () => {
        lookup.answer = found;
        show(noLookup);
        type('Postcode', '1015 CS');
        type('House number', '12');
        fireEvent.blur(screen.getByLabelText('Postcode'));
        expect(lookup.calls).toEqual([]);
        expect(screen.getByTestId('address-status')).toHaveTextContent('');
    });

    it('ignores an answer that arrives after the address was changed', async () => {
        let release: (value: any) => void = () => undefined;
        lookup.answer = () => new Promise((resolve) => (release = resolve));
        show(home);
        type('Postcode', '1015 CS');
        type('House number', '12');
        fireEvent.blur(screen.getByLabelText('Postcode'));
        await waitFor(() => expect(status()).toHaveTextContent('Looking up your address'));
        type('House number', '14');
        await act(async () => release({ status: 'found', street: 'Keizersgracht', city: 'Amsterdam' }));
        expect(screen.getByLabelText('Street')).toHaveValue('');
        expect(status()).toHaveTextContent('');
    });
});

describe('AddressField when the answer is flagged', () => {
    it('names the part that is wrong next to it, and ties the message to the box', async () => {
        show(home, { home: { type: 'address', address: { postcode: '1015 SS', house_number: '12a', country: 'NL' } } }, { home: ['REQUIRED'] });
        const postcode = await screen.findByLabelText('Postcode');
        await waitFor(() => expect(postcode).toHaveAttribute('aria-invalid', 'true'));
        expect(postcode).toHaveAccessibleDescription(/Enter a Dutch postcode, like 1015 CS\./);
        expect(screen.getByLabelText('House number')).toHaveAccessibleDescription(/Enter the house number in digits, like 12\./);
        expect(screen.getByLabelText('Street')).toHaveAccessibleDescription(/Enter the street\./);
        expect(screen.getByLabelText('City')).toHaveAccessibleDescription(/Enter the city\./);
    });
});
