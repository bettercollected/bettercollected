// The answer filters: the chips of what is in force, and the form that adds a condition (a question, an operator its kind
// takes and a value that suits it), in English and Dutch, with axe.
import React from 'react';

import { fireEvent, render, screen, within } from '@testing-library/react';
import i18n from 'i18next';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';
import { catalogue } from '@app/test/report-fixtures';
import { CLAUSES_MAX, ReportClause } from '@app/utils/report';

import ReportAnswerFilters from './report-answer-filters';

const onChange = vi.fn();
const renderFilters = (clauses: ReportClause[] = [], props: Partial<React.ComponentProps<typeof ReportAnswerFilters>> = {}) => render(<ReportAnswerFilters catalogue={catalogue} clauses={clauses} onChange={onChange} {...props} />);
const openForm = () => {
    fireEvent.click(screen.getByRole('button', { name: 'Add answer filter' }));
    return screen.getByRole('form', { name: 'Add answer filter' });
};

afterEach(async () => {
    onChange.mockReset();
    await i18n.changeLanguage('en');
});

describe('the conditions in force', () => {
    const clauses: ReportClause[] = [
        { field: 'q:team', op: 'is', value: 'north' },
        { field: 'q:score', op: 'between', value: [2, 4] }
    ];

    it('shows each as a chip a person can remove, and one that clears them all', () => {
        renderFilters(clauses);
        const list = screen.getByRole('list', { name: 'Answer filters in force' });
        expect(within(list).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['Which team are you in? is North', 'How satisfied are you? is between 2 – 4', 'Clear answer filters']);
        fireEvent.click(within(list).getByRole('button', { name: 'Remove filter: Which team are you in? is North' }));
        expect(onChange).toHaveBeenLastCalledWith([clauses[1]]);
        fireEvent.click(within(list).getByRole('button', { name: 'Clear answer filters' }));
        expect(onChange).toHaveBeenLastCalledWith([]);
    });

    it('says when a condition names a question the form no longer has', () => {
        renderFilters([{ field: 'q:gone', op: 'is_empty' }]);
        expect(screen.getByText('q:gone has no answer (This question is no longer in the form.)')).toBeInTheDocument();
    });

    it('offers nothing to add past the limit, and says why', () => {
        renderFilters(Array.from({ length: CLAUSES_MAX }, () => clauses[0]));
        expect(screen.getByRole('button', { name: 'Add answer filter' })).toBeDisabled();
        expect(screen.getByText(`At most ${CLAUSES_MAX} answer filters.`)).toBeInTheDocument();
    });

    it('shows nothing for a form with no question that takes a condition', () => {
        const { container } = renderFilters([], { catalogue: { ...catalogue, fields: catalogue.fields.map((f) => ({ ...f, filterOps: [] })) } });
        expect(container).toBeEmptyDOMElement();
    });
});

describe('adding a condition', () => {
    it('picks an option of a single-choice question and adds it', () => {
        renderFilters();
        const form = openForm();
        // the first question has the focus
        expect(within(form).getByLabelText('Question')).toHaveFocus();
        expect(within(form).getAllByRole('option').map((o) => o.textContent)).toEqual(expect.arrayContaining(['Which team are you in?', 'is', 'is not', 'is one of', 'North', 'West']));
        fireEvent.change(within(form).getByLabelText('Value'), { target: { value: 'east' } });
        fireEvent.click(within(form).getByRole('button', { name: 'Add' }));
        expect(onChange).toHaveBeenCalledWith([{ field: 'q:team', op: 'is', value: 'east' }]);
        expect(screen.queryByRole('form')).toBeNull();
        // focus goes back to the button that opened it
        expect(screen.getByRole('button', { name: 'Add answer filter' })).toHaveFocus();
    });

    it('offers checkboxes for a list of options and needs at least one', () => {
        renderFilters();
        const form = openForm();
        fireEvent.change(within(form).getByLabelText('Condition'), { target: { value: 'any_of' } });
        const group = within(form).getByRole('group', { name: 'Value' });
        fireEvent.click(within(group).getByLabelText('South'));
        fireEvent.click(within(group).getByLabelText('North'));
        // North was the one picked to start with: unchecking leaves South
        fireEvent.click(within(form).getByRole('button', { name: 'Add' }));
        expect(onChange).toHaveBeenCalledWith([{ field: 'q:team', op: 'any_of', value: ['south'] }]);
    });

    it('cannot be added with no option picked', () => {
        renderFilters();
        const form = openForm();
        fireEvent.change(within(form).getByLabelText('Condition'), { target: { value: 'any_of' } });
        fireEvent.click(within(within(form).getByRole('group', { name: 'Value' })).getByLabelText('North'));
        expect(within(form).getByRole('button', { name: 'Add' })).toBeDisabled();
    });

    it('takes a number for a number question, two for a range, and is not added with one missing', () => {
        renderFilters();
        const form = openForm();
        fireEvent.change(within(form).getByLabelText('Question'), { target: { value: 'q:score' } });
        const add = () => within(form).getByRole('button', { name: 'Add' });
        expect(add()).toBeDisabled();
        fireEvent.change(within(form).getByLabelText('Condition'), { target: { value: 'between' } });
        fireEvent.change(within(form).getByLabelText('From'), { target: { value: '2' } });
        expect(add()).toBeDisabled();
        fireEvent.change(within(form).getByLabelText('To'), { target: { value: '4.5' } });
        expect(add()).toBeEnabled();
        fireEvent.click(add());
        expect(onChange).toHaveBeenCalledWith([{ field: 'q:score', op: 'between', value: [2, 4.5] }]);
    });

    it('refuses a range the wrong way round', () => {
        renderFilters();
        const form = openForm();
        fireEvent.change(within(form).getByLabelText('Question'), { target: { value: 'q:score' } });
        fireEvent.change(within(form).getByLabelText('Condition'), { target: { value: 'between' } });
        fireEvent.change(within(form).getByLabelText('From'), { target: { value: '5' } });
        fireEvent.change(within(form).getByLabelText('To'), { target: { value: '1' } });
        expect(within(form).getByRole('button', { name: 'Add' })).toBeDisabled();
    });

    it('takes yes or no for a yes/no question, and no value for "has no answer"', () => {
        renderFilters();
        const form = openForm();
        fireEvent.change(within(form).getByLabelText('Question'), { target: { value: 'q:remote' } });
        fireEvent.change(within(form).getByLabelText('Value'), { target: { value: 'false' } });
        fireEvent.click(within(form).getByRole('button', { name: 'Add' }));
        expect(onChange).toHaveBeenLastCalledWith([{ field: 'q:remote', op: 'is', value: false }]);
        const again = openForm();
        fireEvent.change(within(again).getByLabelText('Condition'), { target: { value: 'is_empty' } });
        expect(within(again).queryByLabelText('Value')).toBeNull();
        fireEvent.click(within(again).getByRole('button', { name: 'Add' }));
        expect(onChange).toHaveBeenLastCalledWith([{ field: 'q:team', op: 'is_empty' }]);
    });

    it('keeps the conditions already in force when it adds one, and closes on Escape or Cancel', () => {
        renderFilters([{ field: 'q:remote', op: 'is', value: true }]);
        const form = openForm();
        fireEvent.keyDown(within(form).getByLabelText('Question'), { key: 'Escape' });
        expect(screen.queryByRole('form')).toBeNull();
        const second = openForm();
        fireEvent.click(within(second).getByRole('button', { name: 'Add' }));
        expect(onChange).toHaveBeenCalledWith([{ field: 'q:remote', op: 'is', value: true }, { field: 'q:team', op: 'is', value: 'north' }]);
        const third = openForm();
        fireEvent.click(within(third).getByRole('button', { name: 'Cancel' }));
        expect(screen.queryByRole('form')).toBeNull();
    });
});

describe('Dutch and axe', () => {
    it('is in Dutch', async () => {
        await i18n.changeLanguage('nl');
        renderFilters([{ field: 'q:team', op: 'is', value: 'north' }]);
        expect(screen.getByRole('list', { name: 'Actieve antwoordfilters' })).toHaveTextContent('Which team are you in? is North');
        fireEvent.click(screen.getByRole('button', { name: 'Antwoordfilter toevoegen' }));
        const form = screen.getByRole('form', { name: 'Antwoordfilter toevoegen' });
        expect(within(form).getByLabelText('Voorwaarde')).toBeInTheDocument();
        expect(within(form).getByText('is een van')).toBeInTheDocument();
    });

    it('finds no violation with chips, the form and every kind of value', async () => {
        const { container } = renderFilters([{ field: 'q:score', op: '>=', value: 3 }]);
        expect(await axeViolations(container)).toEqual([]);
        const form = openForm();
        expect(await axeViolations(container)).toEqual([]);
        for (const [question, op] of [['q:team', 'any_of'], ['q:score', 'between'], ['q:remote', 'is'], ['q:years', 'is_empty']]) {
            fireEvent.change(within(form).getByLabelText('Question'), { target: { value: question } });
            fireEvent.change(within(form).getByLabelText('Condition'), { target: { value: op } });
            expect(await axeViolations(container)).toEqual([]);
        }
    });
});
