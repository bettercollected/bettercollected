import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { beforeEach, describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { readBuildReport, saveBuildReport } from '@app/utils/ai-build-report';

import AIBuildChecklist from './ai-build-checklist';

const pages = (): StandardFormFieldDto[] =>
    [
        { id: 'page-1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'q-email', index: 0, type: FieldTypes.EMAIL, title: 'What is your email address?' }] } },
        { id: 'page-2', index: 1, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'q-notes', index: 0, type: FieldTypes.LONG_TEXT, title: 'Anything else?' }] } }
    ] as StandardFormFieldDto[];

const seen: { slide?: any; field?: any } = {};

function Editor() {
    const { initFormFields, formFields } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const { activeFieldComponent } = useActiveFieldComponent();
    seen.slide = activeSlideComponent;
    seen.field = activeFieldComponent;
    React.useEffect(() => {
        initFormFields(pages());
    }, []);
    if (!Array.isArray(formFields) || !formFields.length) return null;
    return <AIBuildChecklist formId="form-1" />;
}

function renderEditor() {
    render(
        <Provider>
            <Editor />
        </Provider>
    );
}

describe('AI build checklist in the editor', () => {
    beforeEach(() => sessionStorage.clear());

    it('shows nothing without a build report', () => {
        renderEditor();
        expect(screen.queryByRole('region', { name: 'Check before publishing' })).not.toBeInTheDocument();
    });

    it('lists findings in plain language with links to the questions, and notes', async () => {
        saveBuildReport('form-1', {
            notes: ['1 page jump(s) were left out: they no longer match the pages or questions.'],
            quality: {
                findings: [
                    { code: 'missing_why_we_ask', severity: 'error', where: ['q-email'] },
                    { code: 'missing_section_titles', severity: 'warning', where: ['2'] },
                    { code: 'something_new', severity: 'warning', where: [] }
                ]
            }
        });
        renderEditor();
        const panel = await screen.findByRole('region', { name: 'Check before publishing' });
        expect(panel).toHaveTextContent('without saying why');
        expect(panel).toHaveTextContent('Some pages have no section title.');
        expect(panel).toHaveTextContent('needs a look before publishing');
        expect(panel).toHaveTextContent('1 page jump(s) were left out');

        fireEvent.click(screen.getByRole('button', { name: 'Go to “What is your email address?”' }));
        expect(seen.slide).toEqual({ id: 'page-1', index: 0 });
        expect(seen.field).toEqual({ id: 'q-email', index: 0 });
        fireEvent.click(screen.getByRole('button', { name: 'Go to page 2' }));
        expect(seen.slide).toEqual({ id: 'page-2', index: 1 });
        expect(seen.field).toBeNull();
    });

    it('stays until dismissed, then is gone for good', async () => {
        saveBuildReport('form-1', { notes: [], quality: { findings: [{ code: 'all_required', severity: 'warning', where: [] }] } });
        renderEditor();
        await screen.findByRole('region', { name: 'Check before publishing' });
        fireEvent.click(screen.getByRole('button', { name: 'Dismiss the checklist' }));
        expect(screen.queryByRole('region', { name: 'Check before publishing' })).not.toBeInTheDocument();
        expect(readBuildReport('form-1')).toBeNull();
    });

    it('stores nothing when there is nothing to check', () => {
        expect(saveBuildReport('form-2', { notes: [], quality: { findings: [] } })).toBe(false);
        expect(readBuildReport('form-2')).toBeNull();
    });
});
