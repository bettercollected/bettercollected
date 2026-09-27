import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { newRepeatingGroup } from '@app/utils/repeating-groups';
import RepeatingGroupSettings from '@app/views/molecules/form-builder/repeating-group-settings';
import RepeatingGroupBuilder from './repeating-group-builder';

const form = (): StandardFormFieldDto[] => [{ id: 's1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [newRepeatingGroup('g', 0)] } }];

let latest: StandardFormFieldDto[] = [];

function Harness() {
    const { formFields, initFormFields } = useFormFieldsAtom();
    const [ready, setReady] = React.useState(false);
    React.useEffect(() => {
        initFormFields(form());
        setReady(true);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    latest = formFields;
    if (!ready || !formFields[0]) return null;
    const slide = formFields[0];
    const group = slide.properties!.fields![0];
    return (
        <>
            <RepeatingGroupBuilder field={group} slide={slide} />
            <RepeatingGroupSettings field={group} slide={slide} />
        </>
    );
}

const children = () => latest[0].properties!.fields![0].properties!.fields!;

describe('RepeatingGroupBuilder', () => {
    it('adds, edits and removes group questions', () => {
        render(
            <Provider>
                <Harness />
            </Provider>
        );
        expect(screen.getAllByTestId('group-child')).toHaveLength(1);

        fireEvent.change(screen.getByLabelText('Add a question to the group'), { target: { value: FieldTypes.NUMBER } });
        expect(children().map((c) => c.type)).toEqual([FieldTypes.SHORT_TEXT, FieldTypes.NUMBER]);

        const titles = screen.getAllByLabelText('Question');
        fireEvent.blur(titles[1], { target: { value: 'Monthly income' } });
        expect(children()[1].title).toBe('Monthly income');

        fireEvent.click(screen.getAllByLabelText('Move question up')[1]);
        expect(children()[0].title).toBe('Monthly income');

        fireEvent.click(screen.getAllByLabelText('Remove question')[0]);
        expect(children()).toHaveLength(1);
    });

    it('settings keep min <= max and store the label', () => {
        render(
            <Provider>
                <Harness />
            </Provider>
        );
        fireEvent.change(screen.getByLabelText('At least'), { target: { value: '4' } });
        fireEvent.blur(screen.getByLabelText('At least'));
        expect(screen.getByText('The minimum cannot be above the maximum.')).toBeInTheDocument();
        expect(latest[0].properties!.fields![0].properties!.repeat!.minItems).toBe(1);

        fireEvent.change(screen.getByLabelText('At most'), { target: { value: '6' } });
        fireEvent.blur(screen.getByLabelText('At most'));
        expect(latest[0].properties!.fields![0].properties!.repeat).toMatchObject({ minItems: 4, maxItems: 6 });

        const label = screen.getByPlaceholderText('e.g. Applicant, Employer');
        fireEvent.change(label, { target: { value: 'Employer' } });
        fireEvent.blur(label);
        expect(latest[0].properties!.fields![0].properties!.repeat!.itemLabel).toBe('Employer');
    });
});
