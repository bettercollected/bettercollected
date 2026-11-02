import React from 'react';

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';

import SaveSectionDialog from './save-section-dialog';
import UpdateFromLibraryDialog from './update-from-library-dialog';

afterEach(cleanup);

const saved = (warnings: any[] = []) => ({ id: 's1', name: 'Applicant', version: 1, questionCount: 2, versions: [1], fields: [], containers: [], warnings });

describe('Save as reusable section', () => {
    const open = (save: any, onOpenChange = vi.fn()) => render(<SaveSectionDialog open onOpenChange={onOpenChange} subject="this question" defaultName="Name" save={save} />);

    it('needs a name and sends it trimmed with the description', async () => {
        const save = vi.fn().mockResolvedValue(saved());
        const onOpenChange = vi.fn();
        open(save, onOpenChange);
        fireEvent.change(screen.getByLabelText('Name'), { target: { value: '  ' } });
        expect((screen.getByRole('button', { name: 'Save to library' }) as HTMLButtonElement).disabled).toBe(true);
        fireEvent.change(screen.getByLabelText('Name'), { target: { value: ' Applicant ' } });
        fireEvent.change(screen.getByLabelText('Description (optional)'), { target: { value: ' A person ' } });
        fireEvent.click(screen.getByRole('button', { name: 'Save to library' }));
        await waitFor(() => expect(save).toHaveBeenCalledWith('Applicant', 'A person'));
        await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
    });

    it('lists what the library could not keep before it closes', async () => {
        const save = vi.fn().mockResolvedValue(
            saved([
                { code: 'condition_dropped', fieldId: 'x', title: 'Age' },
                { code: 'calculation_left_out', fieldId: 'y', title: 'Total' }
            ])
        );
        const onOpenChange = vi.fn();
        open(save, onOpenChange);
        fireEvent.click(screen.getByRole('button', { name: 'Save to library' }));
        expect(await screen.findByText(/A show or hide rule of “Age”/)).toBeTruthy();
        expect(screen.getByText(/The calculation “Total” reads questions outside this section/)).toBeTruthy();
        expect(onOpenChange).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole('button', { name: 'Done' }));
        expect(onOpenChange).toHaveBeenCalledWith(false);
    });

    it('stays open when the library refuses', async () => {
        const save = vi.fn().mockResolvedValue(null);
        const onOpenChange = vi.fn();
        open(save, onOpenChange);
        fireEvent.click(screen.getByRole('button', { name: 'Save to library' }));
        await waitFor(() => expect(save).toHaveBeenCalled());
        expect(onOpenChange).not.toHaveBeenCalled();
    });
});

const plan = (changes: any[], extra: any = {}) => ({ sectionId: 's1', version: 3, baseVersion: 2, baseKnown: true, instance: 'i1', changes, fields: [], containers: [], replaceIds: [], ...extra });
const change = (key: string, status: string, extra: any = {}) => ({ key, id: extra.id ?? key, title: `Q ${key}`, status, what: [], modifiedInCopy: false, ...extra });

describe('Update from library', () => {
    it('shows the diff, grouped by what happens, and applies it on confirm', async () => {
        const apply = vi.fn().mockReturnValue(true);
        const onOpenChange = vi.fn();
        const loaded = plan([change('a', 'unchanged'), change('b', 'changed', { what: ['title', 'required'] }), change('c', 'added', { id: null }), change('d', 'removed', { modifiedInCopy: true })]);
        render(<UpdateFromLibraryDialog open onOpenChange={onOpenChange} plan={() => Promise.resolve(loaded)} apply={apply} />);
        expect(await screen.findByText('The library is at version 3: 1 added, 1 changed, 1 removed.')).toBeTruthy();
        const rows = screen.getAllByRole('listitem').map((row) => row.textContent);
        // added, changed, removed, then the unchanged
        expect(rows[0]).toContain('Added');
        expect(rows[1]).toContain('title, required');
        expect(rows[2]).toContain('You also changed this question in the form');
        expect(rows[3]).toContain('Same');
        fireEvent.click(screen.getByRole('button', { name: 'Update this copy' }));
        expect(apply).toHaveBeenCalledWith(loaded);
        expect(onOpenChange).toHaveBeenCalledWith(false);
    });

    it('says when the copy is up to date and when the base version is gone', async () => {
        render(<UpdateFromLibraryDialog open onOpenChange={vi.fn()} plan={() => Promise.resolve(plan([change('a', 'unchanged')], { baseKnown: false }))} apply={vi.fn()} />);
        expect(await screen.findByText('This copy is up to date with the library.')).toBeTruthy();
        expect(screen.getByText(/no longer kept/)).toBeTruthy();
    });

    it('closes when there is nothing to compare', async () => {
        const onOpenChange = vi.fn();
        render(<UpdateFromLibraryDialog open onOpenChange={onOpenChange} plan={() => Promise.resolve(null)} apply={vi.fn()} />);
        await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
    });
});
