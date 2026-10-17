import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { store } from '@app/store/store';
import FieldSettings from '@app/views/organism/field-settings';

import InsertFieldComponent from './insert-field-modal';

const pages = (): StandardFormFieldDto[] => [
    {
        id: 'page-1',
        index: 0,
        type: FieldTypes.SLIDE,
        properties: {
            fields: [
                { id: 'q-1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name' },
                { id: 'q-2', index: 1, type: FieldTypes.EMAIL, title: 'Email' },
                { id: 'q-3', index: 2, type: FieldTypes.SHORT_TEXT, title: 'City' }
            ]
        }
    } as StandardFormFieldDto
];

const seen: { builder?: ReturnType<typeof useFormFieldsAtom>; active?: { id: string; index: number } | null; slide?: { id: string; index: number } | null } = {};

function Editor({ settings = false }: { settings?: boolean }) {
    const builder = useFormFieldsAtom();
    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent();
    const { activeFieldComponent } = useActiveFieldComponent();
    seen.builder = builder;
    seen.active = activeFieldComponent;
    seen.slide = activeSlideComponent;
    React.useEffect(() => {
        builder.initFormFields(pages());
        setActiveSlideComponent({ id: 'page-1', index: 0 });
    }, []);
    if (!builder.formFields[0] || activeSlideComponent?.id !== 'page-1' && !seen.active) return null;
    return (
        <>
            <InsertFieldComponent formFields={builder.formFields} activeSlideComponent={activeSlideComponent} closeDropdown={() => {}} />
            {settings && activeFieldComponent && <FieldSettings />}
        </>
    );
}

function renderEditor(settings = false) {
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Editor settings={settings} />
            </Provider>
        </ReduxProvider>
    );
}

describe('inserting a question', () => {
    it('on a new page selects the new question, not one of the previous page', async () => {
        renderEditor();
        fireEvent.click(await screen.findByLabelText('Insert in new page'));
        await act(async () => fireEvent.click(screen.getByRole('button', { name: /^Email$/ })));

        expect(seen.slide?.index).toBe(1);
        const newPage = seen.builder!.formFields[1];
        const inserted = newPage.properties!.fields![0];
        expect(seen.active).toEqual({ id: inserted.id, index: 0 });
        expect(seen.builder!.activeField?.id).toBe(inserted.id);
    });

    it('on the current page selects the question added at its end', async () => {
        renderEditor();
        fireEvent.click(await screen.findByLabelText('Insert in current page'));
        await act(async () => fireEvent.click(screen.getByRole('button', { name: /^Email$/ })));

        const fields = seen.builder!.formFields[0].properties!.fields!;
        expect(fields).toHaveLength(4);
        expect(seen.active).toEqual({ id: fields[3].id, index: 3 });
        expect(seen.builder!.activeField?.id).toBe(fields[3].id);
    });

    it('the settings panel opens on the new question', async () => {
        renderEditor(true);
        fireEvent.click(await screen.findByLabelText('Insert in new page'));
        await act(async () => fireEvent.click(screen.getByRole('button', { name: /^Email$/ })));
        expect(screen.getByText('Settings')).toBeInTheDocument();
        // not the previous page's last question
        expect(screen.queryByTitle('City')).toBeNull();
    });
});

describe('field settings', () => {
    it('a selection that points at no question shows no settings instead of crashing', async () => {
        function Stale() {
            const builder = useFormFieldsAtom();
            const { setActiveSlideComponent } = useActiveSlideComponent();
            const { setActiveFieldComponent } = useActiveFieldComponent();
            React.useEffect(() => {
                builder.initFormFields(pages());
                setActiveSlideComponent({ id: 'page-1', index: 0 });
                setActiveFieldComponent({ id: 'gone', index: 7 });
            }, []);
            return <FieldSettings />;
        }
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <Stale />
                </Provider>
            </ReduxProvider>
        );
        expect(await screen.findByRole('button', { name: '‹ Back to page' })).toBeInTheDocument();
        expect(screen.queryByText('Settings')).toBeNull();
    });
});
