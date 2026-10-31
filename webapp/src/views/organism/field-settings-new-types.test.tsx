import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { store } from '@app/store/store';

import FieldSettings from './field-settings';

// What the server says about the newer question types (its NEW_QUESTION_TYPES_ENABLED).
const served = vi.hoisted(() => ({ newQuestionTypesEnabled: false }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ newQuestionTypesEnabled: served.newQuestionTypesEnabled }) }));
afterEach(() => {
    served.newQuestionTypesEnabled = false;
});

const question = (type: FieldTypes): StandardFormFieldDto => {
    const base = { id: 'q', index: 0, type, title: 'Question' } as StandardFormFieldDto;
    if (type === FieldTypes.TIME) return { ...base, properties: { minTime: '08:00' } } as StandardFormFieldDto;
    if (type === FieldTypes.CURRENCY) return { ...base, properties: { currencies: ['EUR'] }, validations: { minValue: 5 } } as StandardFormFieldDto;
    return base;
};

function Selected({ type }: { type: FieldTypes }) {
    const builder = useFormFieldsAtom();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();
    React.useEffect(() => {
        builder.initFormFields([{ id: 'page-1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [question(type)] } } as StandardFormFieldDto]);
        setActiveSlideComponent({ id: 'page-1', index: 0 });
        setActiveFieldComponent({ id: 'q', index: 0 });
    }, []);
    return <FieldSettings />;
}

const renderSettings = (type: FieldTypes) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Selected type={type} />
            </Provider>
        </ReduxProvider>
    );

const answerRules = async () => (await screen.findByRole('heading', { name: 'Answer rules' })).closest('section') ?? document.body;

describe('the settings of the newer question types while the server does not take them', () => {
    it.each([FieldTypes.TIME, FieldTypes.DAY, FieldTypes.CURRENCY])('shows a %s question\'s answer settings read-only, with a note', async (type) => {
        renderSettings(type);
        const section = await answerRules();
        const fieldset = section.querySelector('fieldset');
        expect(fieldset).not.toBeNull();
        expect(fieldset).toBeDisabled();
        expect(fieldset).toHaveAttribute('data-locked', 'true');
        for (const control of Array.from(fieldset!.querySelectorAll('input, select, button'))) expect(control).toBeDisabled();
        expect(screen.getByRole('note')).toHaveTextContent(/NEW_TYPES\.LOCKED|can't be changed on this server/);
    });

    it('keeps what every question has editable', async () => {
        renderSettings(FieldTypes.TIME);
        await answerRules();
        expect(screen.getByRole('switch', { name: 'Required' })).not.toBeDisabled();
        expect(screen.getByRole('switch', { name: 'Description' })).not.toBeDisabled();
    });

    it('leaves a date question alone: it is not one of the newer types', async () => {
        renderSettings(FieldTypes.DATE);
        const section = await answerRules();
        const fieldset = section.querySelector('fieldset');
        expect(fieldset).not.toBeDisabled();
        expect(screen.queryByRole('note')).toBeNull();
    });

    it.each([FieldTypes.TIME, FieldTypes.DAY, FieldTypes.CURRENCY])('lets a %s question\'s settings be changed once the server takes them', async (type) => {
        served.newQuestionTypesEnabled = true;
        renderSettings(type);
        const section = await answerRules();
        expect(section.querySelector('fieldset')).not.toBeDisabled();
        expect(screen.queryByRole('note')).toBeNull();
    });
});
