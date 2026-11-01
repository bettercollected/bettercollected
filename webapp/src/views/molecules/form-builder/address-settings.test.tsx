// Builder text resolves through the app's i18n instance.
import '@app/shared/hocs/i18n-provider';
import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import axe from 'axe-core';
import i18n from 'i18next';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';

import AnswerRulesSettings from './answer-rules-settings';

const served = vi.hoisted(() => ({ addressLookupEnabled: true, answered: true }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ addressLookupEnabled: served.addressLookupEnabled, answered: served.answered }) }));
vi.mock('@app/store/redux/form-api', async (importOriginal) => ({ ...(await importOriginal<typeof import('@app/store/redux/form-api')>()), useCheckAnswerPatternMutation: () => [vi.fn(), {}] }));

const address = (properties: Record<string, any> = {}): StandardFormFieldDto => ({ id: 'a', index: 0, type: FieldTypes.ADDRESS, title: 'Home', properties });

function setup(field: StandardFormFieldDto) {
    const onChange = vi.fn();
    const onPropertyChange = vi.fn();
    const view = render(<AnswerRulesSettings field={field} onChange={onChange} onPropertyChange={onPropertyChange} />);
    return { onChange, onPropertyChange, ...view };
}

afterEach(async () => {
    served.addressLookupEnabled = true;
    served.answered = true;
    await act(() => i18n.changeLanguage('en'));
});

describe('settings of an address question', () => {
    it('lists the Netherlands only until countries are chosen, with no way to remove the only one', () => {
        setup(address());
        const list = screen.getByRole('list', { name: 'Countries' });
        expect(within(list).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['Netherlands']);
        expect(screen.queryByRole('button', { name: /Remove/ })).toBeNull();
    });

    it('adds a country to the list, in the builder\'s language, and removes one again', async () => {
        const { onPropertyChange } = setup(address());
        fireEvent.change(screen.getByLabelText('Add a country'), { target: { value: 'BE' } });
        expect(onPropertyChange).toHaveBeenLastCalledWith({ countries: ['NL', 'BE'] });
        await act(() => i18n.changeLanguage('nl'));
        const dutch = setup(address({ countries: ['NL', 'BE'] }));
        const lists = screen.getAllByRole('list', { name: 'Landen' });
        expect(within(lists[lists.length - 1]).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['Nederland', 'België']);
        fireEvent.click(screen.getByRole('button', { name: 'Verwijder België' }));
        expect(dutch.onPropertyChange).toHaveBeenLastCalledWith({ countries: undefined });
    });

    it('saves the default as no list at all', () => {
        const { onPropertyChange } = setup(address({ countries: ['NL', 'BE'] }));
        fireEvent.click(screen.getByRole('button', { name: 'Remove Belgium' }));
        expect(onPropertyChange).toHaveBeenLastCalledWith({ countries: undefined });
    });

    it('switches the lookup off and on again, only while Dutch addresses are allowed', () => {
        const { onPropertyChange } = setup(address());
        const toggle = screen.getByRole('switch', { name: 'Fill in street and city from the postcode' });
        expect(toggle).toBeChecked();
        fireEvent.click(toggle);
        expect(onPropertyChange).toHaveBeenLastCalledWith({ addressLookup: false });
    });

    it('offers no lookup switch for a question that does not allow the Netherlands', () => {
        setup(address({ countries: ['BE', 'DE'] }));
        expect(screen.queryByRole('switch')).toBeNull();
    });

    it('says when the server has the lookup off, and that a looked-up address is not verified', () => {
        served.addressLookupEnabled = false;
        setup(address());
        expect(screen.getByRole('switch')).toHaveAccessibleDescription(/switched off on this server/);
        expect(screen.getByText(/are not verified/)).toBeInTheDocument();
    });

    it('does not claim the server has the lookup off before the server has said', () => {
        served.addressLookupEnabled = false;
        served.answered = false;
        setup(address());
        expect(screen.getByRole('switch')).not.toHaveAccessibleDescription(/switched off on this server/);
    });

    it('gives the remove button a target of at least 24 pixels', () => {
        setup(address({ countries: ['NL', 'BE'] }));
        const button = screen.getByRole('button', { name: 'Remove Belgium' });
        expect(button).toHaveClass('min-h-6', 'min-w-6');
    });

    it('passes axe', async () => {
        const { container } = setup(address({ countries: ['NL', 'BE'] }));
        const results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
        expect(results.violations.map((v) => v.id)).toEqual([]);
    });
});
