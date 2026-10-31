import React from 'react';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider, createStore, useAtomValue } from 'jotai';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { FieldRule } from '@app/lib/field-rules';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { useField } from '@app/store/jotai/entity-hooks';
import { canUndoAtom, dispatchAtom, formDocAtom, resetFromServerAtom, undoAtom } from '@app/store/jotai/form-document';
import { axeViolations } from '@app/test/axe';

import FieldRulesSection from './field-rules-section';
import FieldRulesSettings, { ruleSources, unfinishedReason } from './field-rules-settings';

// What the server says about field rules, with the permissions (its FIELD_RULES_ENABLED).
const served = vi.hoisted(() => ({ fieldRulesEnabled: true }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ fieldRulesEnabled: served.fieldRulesEnabled }) }));

const question = (id: string, type: string, title: string, extra: Record<string, unknown> = {}, properties: Record<string, unknown> = {}): StandardFormFieldDto =>
    ({ id, index: 0, type, title, properties: { fields: [], ...properties }, validations: {}, ...extra }) as unknown as StandardFormFieldDto;

const country = question(
    'country',
    FieldTypes.DROP_DOWN,
    'Country',
    {},
    {
        choices: [
            { id: 'nl', value: 'Netherlands' },
            { id: 'be', value: 'Belgium' }
        ]
    }
);
const postcode = (rules?: FieldRule[]) => question('postcode', FieldTypes.SHORT_TEXT, 'Postcode', {}, rules ? { rules } : {});
const qty = question('qty', FieldTypes.NUMBER, 'Quantity');
const total = (rules?: FieldRule[]) => question('total', FieldTypes.NUMBER, 'Total', {}, rules ? { rules } : {});
const page = (...fields: StandardFormFieldDto[]) => ({ id: 'p1', index: 0, type: FieldTypes.SLIDE, properties: { fields: fields.map((f, index) => ({ ...f, index })) } }) as unknown as StandardFormFieldDto;

const NL: FieldRule = { id: 'r_nl', when: { conditions: [{ fieldId: 'country', fieldType: 'dropdown', comparison: 'IS_EQUAL', value: 'Netherlands' }] }, then: { required: true } };
const BE: FieldRule = { id: 'r_be', when: { conditions: [{ fieldId: 'country', fieldType: 'dropdown', comparison: 'IS_EQUAL', value: 'Belgium' }] }, then: { description: 'Four digits' } };

afterEach(async () => {
    await act(() => i18n.changeLanguage('en'));
});

describe('the rules editor (props)', () => {
    const renderEditor = (rules: FieldRule[] | undefined, onChange = vi.fn(() => true), extra: Partial<React.ComponentProps<typeof FieldRulesSettings>> = {}) => {
        const field = postcode(rules);
        render(<FieldRulesSettings field={field} slides={[page(country, field, qty, total())]} hiddenNames={[]} onChange={onChange} {...extra} />);
        return onChange;
    };

    it('says what rules are and offers to add one, when there are none', () => {
        renderEditor(undefined);
        expect(screen.getByText(/No rules yet/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Add a rule' })).toBeEnabled();
    });

    it('adds a rule with an empty trigger as an unsaved draft: nothing is saved until a condition is picked', () => {
        const onChange = renderEditor(undefined);
        fireEvent.click(screen.getByRole('button', { name: 'Add a rule' }));
        expect(onChange).not.toHaveBeenCalled();
        const card = within(screen.getByTestId('field-rule-1'));
        expect(screen.getByTestId('rule-unfinished')).toHaveTextContent('Finish the condition');
        expect(card.getByRole('combobox', { name: 'Question' })).toHaveDisplayValue('Country');
        fireEvent.change(card.getByRole('combobox', { name: 'Value' }), { target: { value: 'Netherlands' } });
        expect(onChange).toHaveBeenCalledTimes(1);
        const [rules] = onChange.mock.calls[0] as unknown as [FieldRule[]];
        expect(rules).toHaveLength(1);
        expect(rules[0].when.conditions?.[0]).toMatchObject({ fieldId: 'country', comparison: 'IS_EQUAL', value: 'Netherlands' });
        expect(rules[0].then).toEqual({ required: true });
        expect(rules[0].id).toMatch(/^[A-Za-z0-9_-]{1,64}$/);
    });

    it('has no formula fallback: with nothing to read, the empty rule says so and waits', () => {
        const field = postcode();
        const onChange = vi.fn(() => true);
        render(<FieldRulesSettings field={field} slides={[page(field)]} hiddenNames={[]} onChange={onChange} />);
        fireEvent.click(screen.getByRole('button', { name: 'Add a rule' }));
        expect(onChange).not.toHaveBeenCalled();
        expect(screen.getByText(/Add another question/)).toBeInTheDocument();
        expect(screen.getByTestId('rule-unfinished')).toBeInTheDocument();
    });

    it('starts a rule on a repeating group the same way: an empty count condition, not a formula', () => {
        const group = question('people', FieldTypes.GROUP, 'People', {}, { repeat: { minItems: 1, maxItems: 3 }, fields: [question('name', FieldTypes.SHORT_TEXT, 'Name')] });
        const field = postcode();
        const onChange = vi.fn(() => true);
        render(<FieldRulesSettings field={field} slides={[page(group, field)]} hiddenNames={[]} onChange={onChange} />);
        fireEvent.click(screen.getByRole('button', { name: 'Add a rule' }));
        expect(onChange).not.toHaveBeenCalled();
        expect(within(screen.getByTestId('field-rule-1')).getByRole('combobox', { name: 'Group condition' })).toHaveDisplayValue('Number of items');
        expect(screen.queryByLabelText('Formula that must be true')).toBeNull();
    });

    it('lists the rules with a one-line summary each, in order', () => {
        renderEditor([NL, BE]);
        const summaries = screen.getAllByTestId('rule-summary').map((el) => el.textContent);
        expect(summaries).toEqual(['When Country is equal to Netherlands: make required', 'When Country is equal to Belgium: change the description']);
        expect(screen.getByRole('group', { name: 'Rule 1' })).toBeInTheDocument();
        expect(screen.getByRole('group', { name: 'Rule 2' })).toBeInTheDocument();
    });

    it('reorders with buttons and announces it; the ends cannot move further', () => {
        const onChange = renderEditor([NL, BE]);
        expect(screen.getByRole('button', { name: 'Move rule 1 up' })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Move rule 2 down' })).toBeDisabled();
        fireEvent.click(screen.getByRole('button', { name: 'Move rule 2 up' }));
        expect((onChange.mock.calls[0] as unknown as [FieldRule[]])[0].map((r) => r.id)).toEqual(['r_be', 'r_nl']);
        expect(screen.getByRole('status')).toHaveTextContent('Rule moved from position 2 to 1.');
    });

    it('deletes a rule, and the last one clears the list', () => {
        const onChange = renderEditor([NL]);
        fireEvent.click(screen.getByRole('button', { name: 'Delete rule 1' }));
        expect(onChange).toHaveBeenCalledWith(undefined, undefined);
    });

    it('edits the condition with the logic condition rows, and saves a complete one', () => {
        const onChange = renderEditor([NL]);
        const card = within(screen.getByTestId('field-rule-1'));
        fireEvent.change(card.getByDisplayValue('Netherlands'), { target: { value: 'Belgium' } });
        expect((onChange.mock.calls.at(-1) as unknown as [FieldRule[]])[0][0].when.conditions?.[0].value).toBe('Belgium');
    });

    it('keeps an unfinished edit as a draft with a reason, and does not save it', () => {
        const onChange = renderEditor([BE]);
        const card = within(screen.getByTestId('field-rule-1'));
        fireEvent.change(card.getByLabelText('New description'), { target: { value: '' } });
        // an empty description is allowed by the model, so it saves
        expect(onChange).toHaveBeenCalled();
        onChange.mockClear();
        fireEvent.click(card.getByRole('switch', { name: 'Change the label' }));
        expect(onChange).not.toHaveBeenCalled();
        expect(screen.getByTestId('rule-unfinished')).toHaveTextContent('Give the new label some text');
        fireEvent.change(card.getByLabelText('New label'), { target: { value: 'Postcode (NL)' } });
        expect(onChange).toHaveBeenCalledTimes(1);
        expect((onChange.mock.calls[0] as unknown as [FieldRule[], string])[1]).toBe('rules:postcode:r_be:title');
    });

    it('sets a value from a formula, and warns about locking without a value', () => {
        const onChange = renderEditor(
            [{ id: 'r_q', when: { expression: true }, then: { readOnly: true } }],
            vi.fn(() => true)
        );
        expect(screen.getByTestId('warn-read-only-no-value')).toHaveTextContent('discarded');
        const card = within(screen.getByTestId('field-rule-1'));
        fireEvent.click(card.getByRole('switch', { name: 'Set the value' }));
        const [rules] = onChange.mock.calls.at(-1) as unknown as [FieldRule[]];
        expect(rules[0].then).toEqual({ setValue: { expression: 1 } });
    });

    it('offers the options of a choice question and stores the option id', () => {
        const field = question(
            'pick',
            FieldTypes.DROP_DOWN,
            'Pick',
            {},
            {
                choices: [
                    { id: 'a', value: 'A' },
                    { id: 'b', value: 'B' }
                ],
                rules: [{ id: 'r', when: { expression: true }, then: { setValue: { const: 'a' } } }]
            }
        );
        const onChange = vi.fn(() => true);
        render(<FieldRulesSettings field={field} slides={[page(country, field)]} hiddenNames={[]} onChange={onChange} />);
        fireEvent.change(screen.getByLabelText('Option to select'), { target: { value: 'b' } });
        expect((onChange.mock.calls.at(-1) as unknown as [FieldRule[]])[0][0].then.setValue).toEqual({ const: 'b' });
    });

    it('shows the shared checks inline: a rule that reads a question the form no longer has', () => {
        const dangling: FieldRule = { ...NL, when: { conditions: [{ fieldId: 'gone', fieldType: 'dropdown', comparison: 'IS_NOT_EMPTY' }] } };
        renderEditor([dangling]);
        expect(within(screen.getByTestId('field-rule-1')).getByText(/uses 'gone', which is no question of this form/)).toBeInTheDocument();
        // the row does not show another question in its place
        expect(within(screen.getByTestId('field-rule-1')).getByRole('combobox', { name: 'Question' })).toHaveDisplayValue('(question no longer on the form)');
    });

    it('warns about a circle of set values', () => {
        const setFrom = (id: string, from: string): FieldRule => ({ id, when: { expression: true }, then: { setValue: { expression: { '+': [{ var: from }, 1] } } } });
        const a = question('a', FieldTypes.NUMBER, 'A', {}, { rules: [setFrom('ra', 'b')] });
        const b = question('b', FieldTypes.NUMBER, 'B', {}, { rules: [setFrom('rb', 'a')] });
        render(<FieldRulesSettings field={a} slides={[page(a, b)]} hiddenNames={[]} onChange={() => true} />);
        expect(screen.getByText(/in a circle/)).toBeInTheDocument();
    });

    it('stops at the cap of rules a question can have', () => {
        const many = Array.from({ length: 8 }, (_, i): FieldRule => ({ id: `r${i}`, when: { expression: true }, then: { required: true } }));
        renderEditor(many);
        expect(screen.getByRole('button', { name: 'Add a rule' })).toBeDisabled();
        expect(screen.getByText('A question can have at most 8 rules.')).toBeInTheDocument();
    });

    it('lists the rules without editing them when the server does not take rules', () => {
        renderEditor(
            [NL],
            vi.fn(() => true),
            { editable: false }
        );
        expect(screen.getByTestId('field-rules-readonly')).toHaveTextContent('cannot be created or changed on this server yet');
        expect(screen.queryByRole('button', { name: 'Add a rule' })).toBeNull();
    });

    it('speaks Dutch', async () => {
        await act(() => i18n.changeLanguage('nl'));
        renderEditor([NL]);
        expect(screen.getByRole('button', { name: 'Regel toevoegen' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Regel 1 verwijderen' })).toBeInTheDocument();
        expect(screen.getByText('Dan')).toBeInTheDocument();
    });

    it('is operable from the keyboard: every control is a native button, input or select', () => {
        renderEditor([NL, BE]);
        const card = screen.getByTestId('field-rule-1');
        for (const control of card.querySelectorAll('button, input, select, textarea, [role="switch"]')) {
            expect(['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA']).toContain(control.tagName);
            const name = control.getAttribute('aria-label') ?? control.getAttribute('aria-labelledby') ?? (control as HTMLInputElement).labels?.[0]?.textContent ?? control.textContent;
            expect(name?.trim(), control.outerHTML).toBeTruthy();
        }
    });
});

describe('accessibility', () => {
    it.each(['en', 'nl'])('has no WCAG A/AA violations with rules of every kind (%s)', async (language) => {
        await act(() => i18n.changeLanguage(language));
        const onlyFormula: FieldRule = { id: 'r_f', when: { expression: { '>': [{ var: 'qty' }, 3] } }, then: { setValue: { expression: { '*': [{ var: 'qty' }, 5] } }, title: 'Total', description: 'Five times' } };
        const field = total([NL, onlyFormula, { id: 'r_l', when: { expression: true }, then: { readOnly: true } }]);
        const { container } = render(<FieldRulesSettings field={field} slides={[page(country, qty, field)]} hiddenNames={[]} onChange={() => true} />);
        expect(await axeViolations(container)).toEqual([]);
    });
});

describe('accessibility: names, errors and hints', () => {
    const describers = (element: Element) =>
        (element.getAttribute('aria-describedby') ?? '')
            .split(' ')
            .filter(Boolean)
            .map((id) => document.getElementById(id));

    it('points an invalid value input at what is wrong, and marks it invalid', () => {
        const field = postcode([{ id: 'r', when: { expression: true }, then: { setValue: { const: '' } } }]);
        render(<FieldRulesSettings field={field} slides={[page(country, field)]} hiddenNames={[]} onChange={() => true} />);
        const input = within(screen.getByTestId('field-rule-1')).getByLabelText('Value');
        expect(input).toHaveAttribute('aria-invalid', 'true');
        const described = describers(input);
        expect(described.length).toBeGreaterThan(0);
        expect(described.every(Boolean)).toBe(true);
        expect(described.map((el) => el!.textContent).join(' ')).toContain('Give the value');
    });

    it("points the formula and the value formula at the rule's problems", () => {
        const rule: FieldRule = { id: 'r', when: { expression: { '>': [{ var: 'qty' }, 3] } }, then: { setValue: { expression: { '+': [{ var: 'nope' }, 1] } } } };
        const field = total([rule]);
        render(<FieldRulesSettings field={field} slides={[page(qty, field)]} hiddenNames={[]} onChange={() => true} />);
        const formula = screen.getByLabelText('Formula for the value');
        expect(formula).toHaveAttribute('aria-invalid', 'true');
        const text = describers(formula)
            .map((el) => el!.textContent)
            .join(' ');
        expect(text).toContain("uses 'nope'");
        // and the other formula, which is fine, is not marked
        expect(screen.getByLabelText('Formula that must be true')).not.toHaveAttribute('aria-invalid');
    });

    it('marks a condition that waits for its value, and says why', () => {
        const field = postcode([{ id: 'r', when: { conditions: [{ fieldId: 'country', fieldType: 'dropdown', comparison: 'IS_EQUAL', value: '' }] }, then: { required: true } }]);
        render(<FieldRulesSettings field={field} slides={[page(country, field)]} hiddenNames={[]} onChange={() => true} />);
        const value = within(screen.getByTestId('field-rule-1')).getByLabelText('Value');
        expect(value).toHaveAttribute('aria-invalid', 'true');
        expect(describers(value).map((el) => el!.textContent)).toContain('Enter a value for this rule to work.');
    });

    it('has no English left in the condition rows in Dutch', async () => {
        await act(() => i18n.changeLanguage('nl'));
        const field = postcode([NL]);
        render(<FieldRulesSettings field={field} slides={[page(country, field)]} hiddenNames={[]} onChange={() => true} />);
        const card = within(screen.getByTestId('field-rule-1'));
        expect(card.getByRole('combobox', { name: 'Vraag' })).toBeInTheDocument();
        expect(card.getByRole('combobox', { name: 'Vergelijking' })).toHaveDisplayValue('is gelijk aan');
        expect(card.getByLabelText('Waarde')).toBeInTheDocument();
        for (const english of ['Question', 'Comparison', 'is equal to', 'Remove condition', 'Select…']) expect(screen.queryByText(english)).toBeNull();
        expect(screen.getByTestId('rule-summary')).toHaveTextContent('Wanneer Country is gelijk aan Netherlands');
    });
});

describe('helpers', () => {
    it('sources are the other answerable questions, never the question itself', () => {
        const field = postcode();
        expect(ruleSources([page(country, field, qty)], field).map((s) => s.field.id)).toEqual(['country', 'qty']);
    });

    it('says what is left to fill in', () => {
        const field = postcode();
        expect(unfinishedReason({ id: 'r', when: { conditions: [{ fieldId: 'country', comparison: 'IS_EQUAL', value: '' }] }, then: { required: true } }, field)).toBe('TRIGGER');
        expect(unfinishedReason({ id: 'r', when: { expression: true }, then: {} }, field)).toBe('EFFECT');
        expect(unfinishedReason({ id: 'r', when: { expression: true }, then: { title: ' ' } }, field)).toBe('TITLE');
        expect(unfinishedReason({ id: 'r', when: { expression: true }, then: { setValue: { const: '' } } }, field)).toBe('VALUE');
        expect(unfinishedReason(NL, field)).toBeNull();
    });
});

describe('the rules section on the form document', () => {
    function load(rules?: FieldRule[]) {
        const store = createStore();
        store.set(resetFromServerAtom, { formId: 'f', title: 'T', builderVersion: 'v2', fields: [page(country, postcode(rules), qty, total())] } as any);
        return store;
    }
    function Harness() {
        const field = useField('postcode');
        return field ? <FieldRulesSection field={field} /> : null;
    }
    const mount = (store: ReturnType<typeof createStore>, flag = true) => {
        served.fieldRulesEnabled = flag;
        return render(
            <Provider store={store}>
                <Harness />
            </Provider>
        );
    };

    it('shows the editor when the server says it takes rules', () => {
        mount(load(), true);
        expect(screen.getByRole('heading', { name: 'Rules' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Add a rule' })).toBeInTheDocument();
        expect(screen.queryByText(/cannot be created or changed on this server yet/)).toBeNull();
    });

    it('is hidden when the server has rules switched off and the question has none', () => {
        mount(load(), false);
        expect(screen.queryByRole('heading', { name: 'Rules' })).toBeNull();
    });

    it('still lists the rules a question has when rules are switched off', () => {
        mount(load([NL]), false);
        expect(screen.getByTestId('field-rules-readonly')).toHaveTextContent('cannot be created or changed on this server yet');
        expect(screen.queryByRole('button', { name: 'Add a rule' })).toBeNull();
    });

    it('adds, edits, undoes: each edit is a set_field_rules step on the document', () => {
        const store = load();
        mount(store);
        fireEvent.click(screen.getByRole('button', { name: 'Add a rule' }));
        const rulesNow = () => (store.get(formDocAtom).fields![0].properties!.fields![1].properties as any).rules as FieldRule[] | undefined;
        // an empty trigger is a draft: the document has nothing yet
        expect(rulesNow()).toBeUndefined();
        expect(screen.getByTestId('field-rule-1')).toBeInTheDocument();
        fireEvent.change(within(screen.getByTestId('field-rule-1')).getByRole('combobox', { name: 'Value' }), { target: { value: 'Netherlands' } });
        expect(rulesNow()).toHaveLength(1);
        fireEvent.click(screen.getByRole('switch', { name: 'Change the description' }));
        fireEvent.change(screen.getByLabelText('New description'), { target: { value: 'Four digits' } });
        expect(rulesNow()![0].then).toMatchObject({ required: true, description: 'Four digits' });
        act(() => void store.set(undoAtom));
        expect(rulesNow()![0].then).toEqual({ required: true, description: '' });
        while (store.get(canUndoAtom)) act(() => void store.set(undoAtom));
        expect(rulesNow()).toBeUndefined();
        expect(screen.getByText(/No rules yet/)).toBeInTheDocument();
        expect(store.get(canUndoAtom)).toBe(false);
    });

    it('refuses a rule id that is already used on another question', () => {
        const store = load();
        mount(store);
        fireEvent.click(screen.getByRole('button', { name: 'Add a rule' }));
        fireEvent.change(within(screen.getByTestId('field-rule-1')).getByRole('combobox', { name: 'Value' }), { target: { value: 'Netherlands' } });
        const refused = store.set(dispatchAtom, {
            ops: [{ op: 'set_field_rules', fieldId: 'total', rules: [{ id: (store.get(formDocAtom).fields![0].properties!.fields![1].properties as any).rules[0].id, when: { expression: true }, then: { required: true } }] }]
        });
        expect(refused).toBe(false);
    });
});

describe('focus', () => {
    const waitFocus = async (find: () => HTMLElement | null) => {
        await waitFor(() => expect(find()).not.toBeNull());
        await waitFor(() => expect(document.activeElement).toBe(find()));
    };
    const ruleCard = (n: number) => within(screen.getByTestId(`field-rule-${n}`));

    function Section({ rules }: { rules?: FieldRule[] }) {
        // a live copy of the question, so that the editor re-renders with what it saved
        const [current, setCurrent] = React.useState(postcode(rules));
        const slides = [page(country, current, qty, total())];
        const onChange = (next: FieldRule[] | undefined) => {
            setCurrent(postcode(next));
            return true;
        };
        return <FieldRulesSettings field={current} slides={slides} hiddenNames={[]} onChange={onChange} />;
    }

    it('goes to the new rule\'s first control after "Add a rule", the first time and the next', async () => {
        render(<Section />);
        fireEvent.click(screen.getByRole('button', { name: 'Add a rule' }));
        await waitFocus(() => ruleCard(1).getAllByRole('combobox')[0]);
        expect(document.activeElement).toHaveDisplayValue('answers match');
        fireEvent.change(ruleCard(1).getByRole('combobox', { name: 'Value' }), { target: { value: 'Netherlands' } });
        fireEvent.click(screen.getByRole('button', { name: 'Add a rule' }));
        await waitFocus(() => ruleCard(2).getAllByRole('combobox')[0]);
    });

    it('goes to the first control of the first rule when the editor was opened from the closed section', async () => {
        const field = postcode();
        served.fieldRulesEnabled = true;
        const store = createStore();
        store.set(resetFromServerAtom, { formId: 'f', title: 'T', builderVersion: 'v2', fields: [page(country, field, qty, total())] } as any);
        function Harness() {
            const live = useField('postcode');
            return live ? <FieldRulesSection field={live} /> : null;
        }
        render(
            <Provider store={store}>
                <Harness />
            </Provider>
        );
        fireEvent.click(screen.getByRole('button', { name: 'Add a rule' })); // this button goes away
        await waitFocus(() => ruleCard(1).getAllByRole('combobox')[0]);
    });

    it('stays on the moved card: the same button, or the card when that button is now disabled', async () => {
        render(<Section rules={[NL, BE, { ...NL, id: 'r_3' }]} />);
        fireEvent.click(screen.getByRole('button', { name: 'Move rule 2 up' }));
        // rule 2 is now first: its "up" button is disabled, so the card itself
        await waitFocus(() => screen.getByTestId('field-rule-1').querySelector('legend'));
        fireEvent.click(screen.getByRole('button', { name: 'Move rule 1 down' }));
        // the rule that was first is now second, and its "down" button still works: focus stays on that button
        await waitFocus(() => (screen.getByRole('button', { name: 'Move rule 2 down' }).hasAttribute('disabled') ? null : screen.getByRole('button', { name: 'Move rule 2 down' })));
    });

    it('goes to an "Add a rule" button after a delete, also when the last rule is gone', async () => {
        render(<Section rules={[NL, BE]} />);
        fireEvent.click(screen.getByRole('button', { name: 'Delete rule 1' }));
        await waitFocus(() => screen.getByRole('button', { name: 'Add a rule' }));
        fireEvent.click(screen.getByRole('button', { name: 'Delete rule 1' }));
        await waitFocus(() => screen.getByRole('button', { name: 'Add a rule' }));
    });

    it('goes to the closed section\'s own "Add a rule" button when the last rule is deleted from the inspector', async () => {
        served.fieldRulesEnabled = true;
        const store = createStore();
        store.set(resetFromServerAtom, { formId: 'f', title: 'T', builderVersion: 'v2', fields: [page(country, postcode([NL]), qty, total())] } as any);
        function Harness() {
            const live = useField('postcode');
            return live ? <FieldRulesSection field={live} /> : null;
        }
        render(
            <Provider store={store}>
                <Harness />
            </Provider>
        );
        fireEvent.click(screen.getByRole('button', { name: 'Delete rule 1' }));
        // the editor closes (no rules, and it was not opened from the button): its Add button is a new element
        await waitFocus(() => screen.getByRole('button', { name: 'Add a rule' }));
    });
});
