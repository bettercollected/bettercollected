import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { getDateRuleSources } from '@app/utils/date-rules';

import DateFieldSettings from './date-field-settings';

const form = (): StandardFormFieldDto[] => [
    {
        id: 's1',
        index: 0,
        type: FieldTypes.SLIDE,
        properties: {
            fields: [
                { id: 'start', index: 0, type: FieldTypes.DATE, title: 'Start date' },
                { id: 'end', index: 1, type: FieldTypes.DATE, title: 'End date' }
            ]
        }
    }
];

let latest: StandardFormFieldDto[] = [];

function Harness() {
    const { formFields, initFormFields, updateFieldProperty } = useFormFieldsAtom();
    const [ready, setReady] = React.useState(false);
    React.useEffect(() => {
        initFormFields(form());
        setReady(true);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    latest = formFields;
    if (!ready || !formFields[0]) return null;
    const end = formFields[0].properties!.fields![1];
    return <DateFieldSettings field={end} sources={getDateRuleSources(formFields, end.id)} onChange={(patch) => Object.entries(patch).forEach(([key, value]) => updateFieldProperty(1, 0, key, value))} />;
}

const endProps = () => latest[0].properties!.fields![1].properties!;

describe('DateFieldSettings', () => {
    it('stores the label and edits date rules on earlier dates, today or a fixed date', () => {
        render(
            <Provider>
                <Harness />
            </Provider>
        );
        const label = screen.getByPlaceholderText('e.g. Start date');
        fireEvent.change(label, { target: { value: ' End date ' } });
        fireEvent.blur(label);
        expect(endProps().label).toBe('End date');

        fireEvent.click(screen.getByText('+ Add date rule'));
        expect(endProps().dateRules).toEqual([{ comparison: 'after', target: 'field', fieldId: 'start' }]);
        // Titles shown, ids stored.
        expect(screen.getByRole('option', { name: 'Start date' })).toHaveValue('field:start');

        fireEvent.change(screen.getByLabelText('Rule 1 comparison'), { target: { value: 'on_or_after' } });
        expect(endProps().dateRules![0].comparison).toBe('on_or_after');

        fireEvent.change(screen.getByLabelText('Rule 1 compares with'), { target: { value: 'date' } });
        expect(endProps().dateRules![0]).toMatchObject({ comparison: 'on_or_after', target: 'date' });
        fireEvent.change(screen.getByLabelText('Rule 1 date'), { target: { value: '2026-03-12' } });
        expect(endProps().dateRules![0]).toEqual({ comparison: 'on_or_after', target: 'date', date: '2026-03-12' });

        fireEvent.change(screen.getByLabelText('Rule 1 compares with'), { target: { value: 'today' } });
        expect(endProps().dateRules![0]).toEqual({ comparison: 'on_or_after', target: 'today' });

        fireEvent.click(screen.getByLabelText('Remove rule 1'));
        expect(endProps().dateRules).toBeUndefined();
    });

    it('stops at five rules', () => {
        render(
            <Provider>
                <Harness />
            </Provider>
        );
        for (let i = 0; i < 5; i++) fireEvent.click(screen.getByText('+ Add date rule'));
        expect(endProps().dateRules).toHaveLength(5);
        expect(screen.queryByText('+ Add date rule')).not.toBeInTheDocument();
    });
});
