// The views bar: open a saved view, save the report as one (for the member alone, or for everyone who can open the
// report when they may edit the form), update, rename, share and delete, and what each refusal says, in English and Dutch.
import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';
import { ReportDefinition, ReportView, ReportViewList } from '@app/utils/report';

import ReportViews, { viewErrorText } from './report-views';

const api = vi.hoisted(() => ({ create: vi.fn(), update: vi.fn(), remove: vi.fn() }));
vi.mock('@app/store/workspaces/api', () => ({
    useCreateReportViewMutation: () => [api.create, { isLoading: false }],
    useUpdateReportViewMutation: () => [api.update, { isLoading: false }],
    useDeleteReportViewMutation: () => [api.remove, { isLoading: false }]
}));

const definition: ReportDefinition = { v: 1, filters: {}, tz: 'Europe/Amsterdam', cards: [{ id: 'c1', kind: 'bar', dimension: { field: 'q:team' }, measures: [{ agg: 'count' }] }] };
const made = (changes: Partial<ReportView> = {}): ReportView => ({
    id: 'a'.repeat(24),
    name: 'Weekly',
    scope: 'private',
    mine: true,
    ownerName: null,
    revision: 1,
    createdAt: null,
    updatedAt: null,
    definition,
    canEdit: true,
    canDelete: true,
    ...changes
});
const mine = made();
const shared = made({ id: 'b'.repeat(24), name: 'Board', scope: 'form', mine: false, ownerName: 'Sanne de Vries', canEdit: true, canDelete: false });
const list = (canShare = true, views = [mine, shared]): ReportViewList => ({ views, canShare, limits: { nameMax: 80, formViews: 50, privateViews: 20 } });

const handlers = { onOpen: vi.fn(), onMark: vi.fn(), onReload: vi.fn() };
const renderBar = (props: Partial<React.ComponentProps<typeof ReportViews>> = {}) =>
    render(<ReportViews workspaceId="ws" formId="f" list={list()} modified={false} definition={definition} canSave {...handlers} {...props} />);
const reply = (value: unknown) => ({ unwrap: () => Promise.resolve(value) });
const refuse = (status: number, code?: string) => ({ unwrap: () => Promise.reject({ status, data: code ? { code } : undefined }) });

beforeEach(() => {
    Object.values({ ...api, ...handlers }).forEach((fn) => fn.mockReset());
});
afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('opening a view', () => {
    it('lists the Overview, then my views and the form\'s own, in two groups', () => {
        renderBar();
        const select = screen.getByRole('combobox', { name: 'Views' });
        expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['Overview', 'Weekly', 'Board']);
        expect(within(select).getByRole('group', { name: 'My views' })).toBeInTheDocument();
        expect(within(select).getByRole('group', { name: 'Views of this form' })).toBeInTheDocument();
    });

    it('opens the chosen view, or the Overview', () => {
        renderBar({ current: mine });
        fireEvent.change(screen.getByRole('combobox', { name: 'Views' }), { target: { value: shared.id } });
        expect(handlers.onOpen).toHaveBeenLastCalledWith(shared);
        fireEvent.change(screen.getByRole('combobox', { name: 'Views' }), { target: { value: '' } });
        expect(handlers.onOpen).toHaveBeenLastCalledWith(null);
    });

    it('says who a view is for and who made it', () => {
        const { rerender } = renderBar({ current: mine });
        expect(screen.getByText('Only you can open this view.')).toBeInTheDocument();
        rerender(<ReportViews workspaceId="ws" formId="f" list={list()} current={shared} modified={false} definition={definition} canSave {...handlers} />);
        expect(screen.getByText('Everyone who can open this report can use this view.')).toBeInTheDocument();
        expect(screen.getByText('Made by Sanne de Vries')).toBeInTheDocument();
        rerender(<ReportViews workspaceId="ws" formId="f" list={list()} current={{ ...shared, ownerName: null }} modified={false} definition={definition} canSave {...handlers} />);
        expect(screen.getByText('Made by a former member')).toBeInTheDocument();
        rerender(<ReportViews workspaceId="ws" formId="f" list={list()} current={{ ...shared, mine: true }} modified={false} definition={definition} canSave {...handlers} />);
        expect(screen.getByText('Made by you')).toBeInTheDocument();
    });

    it('says when the report on screen has changed since the view was saved', () => {
        renderBar({ current: mine, modified: true });
        expect(screen.getByText('Changed since it was saved')).toBeInTheDocument();
    });

    it('says the saved views could not be loaded', () => {
        renderBar({ list: undefined, failed: true });
        expect(screen.getByRole('alert')).toHaveTextContent('The saved views could not be loaded.');
    });
});

describe('saving the report as a view', () => {
    it('saves it privately by default, with the definition on screen, and marks the new view', async () => {
        api.create.mockReturnValue(reply(made({ id: 'c'.repeat(24), name: 'Mine' })));
        renderBar();
        fireEvent.click(screen.getByRole('button', { name: 'Save view' }));
        const form = screen.getByRole('form', { name: 'Save view' });
        expect(within(form).getByLabelText('Only me')).toBeChecked();
        // the name field has the focus, and takes the name
        expect(within(form).getByLabelText('Name')).toHaveFocus();
        fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'Mine' } });
        fireEvent.click(within(form).getByRole('button', { name: 'Save view' }));
        await waitFor(() => expect(api.create).toHaveBeenCalledWith({ workspaceId: 'ws', formId: 'f', name: 'Mine', scope: 'private', definition }));
        await waitFor(() => expect(handlers.onMark).toHaveBeenCalledWith(expect.objectContaining({ name: 'Mine' })));
        expect(screen.queryByRole('form')).toBeNull();
        expect(screen.getByText('View saved')).toBeInTheDocument();
        // focus goes back to the button that opened it
        expect(screen.getByRole('button', { name: 'Save view' })).toHaveFocus();
    });

    it('saves it for the whole form when the member may edit the form', async () => {
        api.create.mockReturnValue(reply(made({ scope: 'form' })));
        renderBar();
        fireEvent.click(screen.getByRole('button', { name: 'Save view' }));
        const form = screen.getByRole('form', { name: 'Save view' });
        expect(within(form).getByText('Shared views are visible to everyone with access to this form.')).toBeInTheDocument();
        fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'Board' } });
        fireEvent.click(within(form).getByLabelText('Everyone who can open this report'));
        fireEvent.click(within(form).getByRole('button', { name: 'Save view' }));
        await waitFor(() => expect(api.create).toHaveBeenCalledWith(expect.objectContaining({ name: 'Board', scope: 'form' })));
    });

    it('offers no sharing to a member who may not edit the form, and saves privately', async () => {
        api.create.mockReturnValue(reply(made()));
        renderBar({ list: list(false) });
        fireEvent.click(screen.getByRole('button', { name: 'Save view' }));
        const form = screen.getByRole('form', { name: 'Save view' });
        expect(within(form).getByLabelText('Everyone who can open this report')).toBeDisabled();
        expect(within(form).getByText('Only people who may edit this form can share a view.')).toBeInTheDocument();
        fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'Notes' } });
        fireEvent.click(within(form).getByRole('button', { name: 'Save view' }));
        await waitFor(() => expect(api.create).toHaveBeenCalledWith(expect.objectContaining({ scope: 'private' })));
    });

    it('cannot be sent without a name, and Escape closes it', () => {
        renderBar();
        fireEvent.click(screen.getByRole('button', { name: 'Save view' }));
        const form = screen.getByRole('form', { name: 'Save view' });
        expect(within(form).getByRole('button', { name: 'Save view' })).toBeDisabled();
        fireEvent.change(within(form).getByLabelText('Name'), { target: { value: '   ' } });
        expect(within(form).getByRole('button', { name: 'Save view' })).toBeDisabled();
        fireEvent.keyDown(within(form).getByLabelText('Name'), { key: 'Escape' });
        expect(screen.queryByRole('form')).toBeNull();
        expect(api.create).not.toHaveBeenCalled();
    });

    it('is not offered when there is nothing to save', () => {
        renderBar({ canSave: false });
        expect(screen.queryByRole('button', { name: /Save/ })).toBeNull();
    });

    it.each([
        [409, 'view_name_taken', 'Another view already has this name.'],
        [409, 'view_limit', 'You have reached the number of saved views allowed here. Delete one first.'],
        [403, 'view_forbidden', 'You may not do this with this view.'],
        [422, 'invalid_view', 'This view cannot be saved as it is. Check the name.'],
        [500, undefined, 'The view could not be saved. Try again.']
    ])('says why a save was refused (%s %s) and keeps the form open', async (status, code, text) => {
        api.create.mockReturnValue(refuse(status, code));
        renderBar();
        fireEvent.click(screen.getByRole('button', { name: 'Save view' }));
        const form = screen.getByRole('form', { name: 'Save view' });
        fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'Mine' } });
        fireEvent.click(within(form).getByRole('button', { name: 'Save view' }));
        expect(await within(form).findByRole('alert')).toHaveTextContent(text);
        expect(handlers.onMark).not.toHaveBeenCalled();
    });
});

describe('changing a view', () => {
    it('offers Update only while the report differs from it, and sends the definition with the revision it was read at', async () => {
        const { rerender } = renderBar({ current: made({ revision: 4 }) });
        expect(screen.queryByRole('button', { name: 'Update view' })).toBeNull();
        rerender(<ReportViews workspaceId="ws" formId="f" list={list()} current={made({ revision: 4 })} modified definition={definition} canSave {...handlers} />);
        api.update.mockReturnValue(reply(made({ revision: 5 })));
        fireEvent.click(screen.getByRole('button', { name: 'Update view' }));
        await waitFor(() => expect(api.update).toHaveBeenCalledWith({ workspaceId: 'ws', formId: 'f', viewId: mine.id, revision: 4, definition }));
        expect(await screen.findByText('View updated')).toBeInTheDocument();
    });

    it('does not offer Update while cards of the view are hidden from this person, only a save as a new view', async () => {
        const { container } = renderBar({ current: made({ revision: 4 }), modified: true, hiddenCards: 2 });
        const update = screen.getByRole('button', { name: 'Update view' });
        expect(update).toBeDisabled();
        expect(update).toHaveAccessibleDescription(/2 cards of this view cannot be shown to you/);
        fireEvent.click(update);
        expect(api.update).not.toHaveBeenCalled();
        // a rename or a change of who sees it does not touch the cards
        expect(screen.getByRole('button', { name: 'Rename or share' })).toBeEnabled();
        expect(await axeViolations(container)).toEqual([]);
        // saving as a new view stays possible
        fireEvent.click(screen.getByRole('button', { name: 'Save as new view' }));
        expect(screen.getByRole('form', { name: 'Save view' })).toBeInTheDocument();
    });

    it('says so in Dutch, and in the singular for one card', async () => {
        await i18n.changeLanguage('nl');
        renderBar({ current: made({ revision: 4 }), modified: true, hiddenCards: 1 });
        expect(screen.getByText(/1 kaart van deze weergave kan niet aan u worden getoond/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Weergave bijwerken' })).toBeDisabled();
    });

    it('offers no update, rename or delete of a view of the form to a member who may not', () => {
        renderBar({ current: { ...shared, canEdit: false, canDelete: false } });
        for (const name of ['Update view', 'Rename or share', 'Delete view']) expect(screen.queryByRole('button', { name })).toBeNull();
    });

    it('renames and moves a view between private and the form\'s, sending only what changed', async () => {
        api.update.mockReturnValue(reply(made({ name: 'Renamed' })));
        renderBar({ current: mine });
        fireEvent.click(screen.getByRole('button', { name: 'Rename or share' }));
        const form = screen.getByRole('form', { name: 'Rename or share' });
        expect(within(form).getByLabelText('Name')).toHaveValue('Weekly');
        fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'Renamed' } });
        fireEvent.click(within(form).getByLabelText('Everyone who can open this report'));
        fireEvent.click(within(form).getByRole('button', { name: 'Done' }));
        await waitFor(() => expect(api.update).toHaveBeenCalledWith({ workspaceId: 'ws', formId: 'f', viewId: mine.id, revision: 1, name: 'Renamed', scope: 'form' }));
        await waitFor(() => expect(screen.queryByRole('form')).toBeNull());
    });

    it('asks the server for nothing when nothing changed', async () => {
        renderBar({ current: mine });
        fireEvent.click(screen.getByRole('button', { name: 'Rename or share' }));
        fireEvent.click(within(screen.getByRole('form', { name: 'Rename or share' })).getByRole('button', { name: 'Done' }));
        await waitFor(() => expect(screen.queryByRole('form')).toBeNull());
        expect(api.update).not.toHaveBeenCalled();
    });

    it('says a view was changed by someone else and loads the views again', async () => {
        api.update.mockReturnValue(refuse(409, 'view_changed'));
        renderBar({ current: mine, modified: true });
        fireEvent.click(screen.getByRole('button', { name: 'Update view' }));
        expect(await screen.findByRole('alert')).toHaveTextContent('This view was changed by someone else. Reload to see it.');
        expect(handlers.onReload).toHaveBeenCalled();
    });
});

describe('a card a condition on an answer cannot be combined with', () => {
    it('says why a save was refused for it, in English and in Dutch', async () => {
        api.create.mockReturnValue(refuse(422, 'op_not_allowed'));
        const { container } = renderBar();
        fireEvent.click(screen.getByRole('button', { name: 'Save view' }));
        const form = screen.getByRole('form', { name: 'Save view' });
        fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'Mine' } });
        fireEvent.click(within(form).getByRole('button', { name: 'Save view' }));
        expect(await within(form).findByRole('alert')).toHaveTextContent('cannot be saved together with a condition on an answer');
        expect(await axeViolations(container)).toEqual([]);
        expect(viewErrorText('op_not_allowed', 422, (key) => i18n.t(key))).toContain('condition on an answer');
        await i18n.changeLanguage('nl');
        expect(viewErrorText('op_not_allowed', 422, (key) => i18n.t(key))).toContain('voorwaarde op een antwoord');
    });
});

describe('deleting a view', () => {
    it('asks first, names the view, and then deletes it and unmarks it', async () => {
        api.remove.mockReturnValue(reply(null));
        renderBar({ current: mine });
        fireEvent.click(screen.getByRole('button', { name: 'Delete view' }));
        const group = screen.getByRole('group', { name: 'Delete view' });
        expect(group).toHaveTextContent('Delete "Weekly"?');
        expect(api.remove).not.toHaveBeenCalled();
        fireEvent.click(within(group).getByRole('button', { name: 'Delete view' }));
        await waitFor(() => expect(api.remove).toHaveBeenCalledWith({ workspaceId: 'ws', formId: 'f', viewId: mine.id, revision: 1 }));
        await waitFor(() => expect(handlers.onMark).toHaveBeenCalledWith(null));
        expect(await screen.findByText('View deleted')).toBeInTheDocument();
    });

    it('says a view of the form disappears for everyone, and can be cancelled', () => {
        renderBar({ current: { ...shared, canDelete: true } });
        fireEvent.click(screen.getByRole('button', { name: 'Delete view' }));
        const group = screen.getByRole('group', { name: 'Delete view' });
        expect(group).toHaveTextContent('It disappears for everyone who can open this report.');
        fireEvent.click(within(group).getByRole('button', { name: 'Cancel' }));
        expect(screen.queryByRole('group', { name: 'Delete view' })).toBeNull();
        expect(api.remove).not.toHaveBeenCalled();
    });
});

describe('Dutch', () => {
    it('is Weergaven, with every control and refusal in Dutch', async () => {
        await i18n.changeLanguage('nl');
        api.create.mockReturnValue(refuse(409, 'view_name_taken'));
        renderBar({ current: mine, modified: true });
        expect(screen.getByRole('combobox', { name: 'Weergaven' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Weergave bijwerken' })).toBeInTheDocument();
        expect(screen.getByText('Gewijzigd sinds het opslaan')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Opslaan als nieuwe weergave' }));
        const form = screen.getByRole('form', { name: 'Weergave opslaan' });
        fireEvent.change(within(form).getByLabelText('Naam'), { target: { value: 'Mijn' } });
        fireEvent.click(within(form).getByRole('button', { name: 'Weergave opslaan' }));
        expect(await within(form).findByRole('alert')).toHaveTextContent('Een andere weergave heeft al deze naam.');
        expect(within(form).getByLabelText('Alleen ik')).toBeInTheDocument();
    });
});

describe('axe', () => {
    it('finds no violation in the bar, its forms and its confirmation', async () => {
        const { container } = renderBar({ current: mine, modified: true });
        expect(await axeViolations(container)).toEqual([]);
        fireEvent.click(screen.getByRole('button', { name: 'Rename or share' }));
        expect(await axeViolations(container)).toEqual([]);
        fireEvent.click(screen.getByRole('button', { name: 'Delete view' }));
        expect(await axeViolations(container)).toEqual([]);
        fireEvent.click(screen.getByRole('button', { name: 'Save as new view' }));
        expect(await axeViolations(container)).toEqual([]);
    });
});
