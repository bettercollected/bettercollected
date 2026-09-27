import React from 'react';

import { act, fireEvent, render, renderHook, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Comparison, LogicalOperator, LogicCondition } from '@app/models/types/form-builder-shared';
import { stringTitleToDoc } from '@app/utils/answer-piping';
import { getGroupPipeOptions, newGroupChild, newRepeatingGroup, remapGroupChildIds, remapTextTokens } from '@app/utils/repeating-groups';
import { ConditionRow, isConditionComplete, newConditionFor } from '@app/views/molecules/form-builder/condition-editor-shared';
import useFormFieldsAtom from './field-selectors';

const setup = () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => <Provider>{children}</Provider>;
    return renderHook(() => useFormFieldsAtom(), { wrapper });
};

let counter = 0;
const ids = () => `id-${++counter}`;

const groupForm = (): StandardFormFieldDto[] => {
    const group = newRepeatingGroup('g', 0, ids);
    group.properties!.fields!.push({ ...newGroupChild(FieldTypes.NUMBER, 1, ids), title: 'Age' });
    const [name, age] = group.properties!.fields!;
    age.properties!.logic = { action: 'SHOW', operator: LogicalOperator.AND, conditions: [{ fieldId: name.id, fieldType: FieldTypes.SHORT_TEXT, comparison: Comparison.IS_NOT_EMPTY, value: '' }] };
    const summary: StandardFormFieldDto = {
        id: 'summary',
        index: 1,
        type: FieldTypes.SHORT_TEXT,
        properties: { logic: { action: 'SHOW', operator: LogicalOperator.AND, conditions: [{ fieldId: 'g', fieldType: 'group', groupMode: 'ANY', childFieldId: age.id, childFieldType: FieldTypes.NUMBER, comparison: Comparison.GREATER_THAN, value: 3 }] } }
    };
    return [{ id: 's1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [group, summary] } }];
};

describe('new repeating group', () => {
    it('starts with one required question, sensible limits and a piped item header', () => {
        const group = newRepeatingGroup('g', 0, ids);
        const [name] = group.properties!.fields!;
        expect(group.type).toBe(FieldTypes.GROUP);
        expect(group.properties?.repeat).toMatchObject({ minItems: 1, maxItems: 3, itemLabel: 'Person', itemTitle: `{{field:${name.id}}}` });
        expect(name.validations?.required).toBe(true);
    });

    it('choice questions get two options', () => {
        expect(newGroupChild(FieldTypes.DROP_DOWN, 0, ids).properties?.choices).toHaveLength(2);
    });
});

describe('builder store — group questions', () => {
    it('adds, reorders and removes questions; removing prunes rules that used them', () => {
        const { result } = setup();
        act(() => result.current.initFormFields(groupForm()));
        const group = () => result.current.formFields[0].properties!.fields![0];
        const [name, age] = group().properties!.fields!;

        act(() => result.current.updateGroupChildren(0, 'g', [age, name]));
        expect(group().properties!.fields!.map((c) => [c.id, c.index])).toEqual([
            [age.id, 0],
            [name.id, 1]
        ]);

        act(() => result.current.updateGroupChildren(0, 'g', [name]));
        // The summary's ANY rule referenced the removed question.
        expect(result.current.formFields[0].properties!.fields![1].properties?.logic).toBeUndefined();
        expect(result.current.canUndo).toBe(true);
    });

    it('updates repeat settings', () => {
        const { result } = setup();
        act(() => result.current.initFormFields(groupForm()));
        act(() => result.current.updateGroupRepeat(0, 'g', { maxItems: 8, itemLabel: 'Employer' }));
        expect(result.current.formFields[0].properties!.fields![0].properties?.repeat).toMatchObject({ minItems: 1, maxItems: 8, itemLabel: 'Employer' });
    });

    it('duplicating a group gives its questions new ids and keeps sibling rules inside the copy', () => {
        const { result } = setup();
        act(() => result.current.initFormFields(groupForm()));
        act(() => result.current.duplicateField(0, 0));
        const [original, copy] = result.current.formFields[0].properties!.fields!;
        const [copyName, copyAge] = copy.properties!.fields!;
        expect(copy.id).not.toBe(original.id);
        expect(copyName.id).not.toBe(original.properties!.fields![0].id);
        expect(copyAge.properties?.logic?.conditions[0].fieldId).toBe(copyName.id);
        expect(copy.properties?.repeat?.itemTitle).toBe(`{{field:${copyName.id}}}`);
    });

    it('duplicating a page remaps group questions and group conditions', () => {
        const { result } = setup();
        act(() => result.current.initFormFields(groupForm()));
        act(() => {
            result.current.duplicateSlide(0);
        });
        const [, copy] = result.current.formFields;
        const [copyGroup, copySummary] = copy.properties!.fields!;
        const condition = copySummary.properties?.logic?.conditions[0] as LogicCondition;
        expect(condition.fieldId).toBe(copyGroup.id);
        expect(condition.childFieldId).toBe(copyGroup.properties!.fields![1].id);
    });
});

describe('helpers', () => {
    it('remaps ids inside text tokens, leaving hidden fields alone', () => {
        expect(remapTextTokens('{{field:a}} {{group:g:sum:a|0}} {{hidden:a}}', { a: 'b', g: 'h' })).toBe('{{field:b}} {{group:h:sum:b|0}} {{hidden:a}}');
    });

    it('remapGroupChildIds returns the id map', () => {
        const group = newRepeatingGroup('g', 0, ids);
        const before = group.properties!.fields![0].id;
        const map = remapGroupChildIds(group, ids);
        expect(map[before]).toBe(group.properties!.fields![0].id);
    });

    it('offers count, lists and numeric aggregates as pipes', () => {
        const form = groupForm();
        const labels = getGroupPipeOptions(form[0].properties!.fields![0], 'People').map((o) => o.label);
        expect(labels).toEqual(['People · number of items', 'People · list of Full name', 'People · list of Age', 'People · sum of Age', 'People · average of Age', 'People · minimum of Age', 'People · maximum of Age']);
    });

    it('string titles become pipe documents (answers render as text)', () => {
        expect(stringTitleToDoc('Hi {{field:n|there}}!')).toEqual({
            type: 'doc',
            content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Hi ' }, { type: 'answerPipe', attrs: { kind: 'field', pipeKey: 'n', label: 'n', fallback: 'there' } }, { type: 'text', text: '!' }] }]
        });
    });
});

describe('condition editor — groups as a whole', () => {
    const form = groupForm();
    const group = form[0].properties!.fields![0];
    const sources = [{ field: group, label: 'People' }];

    it('a group source defaults to an item-count condition', () => {
        const condition = newConditionFor(sources);
        expect(condition).toMatchObject({ fieldId: 'g', groupMode: 'COUNT', comparison: Comparison.GREATER_THAN_EQUAL });
        expect(isConditionComplete({ ...condition, value: 2 })).toBe(true);
        expect(isConditionComplete({ ...condition, groupMode: 'ANY', childFieldId: undefined, value: 2 })).toBe(false);
    });

    it('offers number of items / any item / all items, and the question for any/all', () => {
        let latest: Partial<LogicCondition> = {};
        const condition = newConditionFor(sources);
        const { rerender } = render(<ConditionRow condition={condition} sources={sources} onChange={(patch) => (latest = patch)} />);
        expect(screen.getByRole('option', { name: 'is at least' })).toBeInTheDocument();
        fireEvent.change(screen.getByLabelText('Group condition'), { target: { value: 'ALL' } });
        expect(latest).toMatchObject({ groupMode: 'ALL', childFieldId: group.properties!.fields![0].id });
        rerender(<ConditionRow condition={{ ...condition, ...latest } as LogicCondition} sources={sources} onChange={(patch) => (latest = patch)} />);
        expect(screen.getByLabelText('Question in each item')).toBeInTheDocument();
    });
});
