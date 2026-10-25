// The shared "more" menu (three dots + Remove) on group members, group forms,
// groups and a form's integrations: a named button that opens a menu with the
// keyboard, and the settings rows and integration switches it sits next to.
import React from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { Switch } from '@app/shadcn/components/ui/switch';
import { axeViolations } from '@app/test/axe';

import { SettingRow } from '../dashboard/form-settings';
import DeleteDropDown from './delete-dropdown';

import commonEn from '../../../public/locales/en/common.json';
import commonNl from '../../../public/locales/nl/common.json';

const keyboardOpen = (element: HTMLElement) => {
    element.focus();
    fireEvent.keyDown(element, { key: 'Enter' });
};

describe('DeleteDropDown', () => {
    it('is a button named after what it acts on, announcing a closed menu', async () => {
        const { container } = render(<DeleteDropDown itemName="Job application" onDropDownItemClick={vi.fn()} />);
        const trigger = screen.getByRole('button', { name: 'More actions for Job application' });
        expect(trigger.tagName).toBe('BUTTON');
        expect(trigger).toHaveAttribute('type', 'button');
        expect(trigger).toHaveAttribute('aria-haspopup', 'menu');
        expect(trigger).toHaveAttribute('aria-expanded', 'false');
        expect(await axeViolations(container)).toEqual([]);
    });

    it('falls back to "More actions" without an item name', () => {
        render(<DeleteDropDown onDropDownItemClick={vi.fn()} />);
        expect(screen.getByRole('button', { name: 'More actions' })).toBeInTheDocument();
    });

    it('opens with Enter, focuses the item, and Escape closes it and returns focus', async () => {
        render(<DeleteDropDown itemName="Job application" onDropDownItemClick={vi.fn()} />);
        const trigger = screen.getByRole('button', { name: 'More actions for Job application' });

        keyboardOpen(trigger);
        const menu = await screen.findByRole('menu');
        const item = screen.getByRole('menuitem', { name: 'Remove' });
        expect(trigger).toHaveAttribute('aria-expanded', 'true');
        expect(menu).toHaveAttribute('aria-labelledby', trigger.id);
        await waitFor(() => expect(item).toHaveFocus());
        expect(await axeViolations(document.body)).toEqual([]);

        fireEvent.keyDown(item, { key: 'Escape' });
        await waitFor(() => expect(screen.queryByRole('menu')).toBeNull());
        expect(trigger).toHaveAttribute('aria-expanded', 'false');
        await waitFor(() => expect(trigger).toHaveFocus());
    });

    it('opens with Space too', async () => {
        render(<DeleteDropDown itemName="Job application" onDropDownItemClick={vi.fn()} />);
        const trigger = screen.getByRole('button', { name: 'More actions for Job application' });
        trigger.focus();
        fireEvent.keyDown(trigger, { key: ' ' });
        expect(await screen.findByRole('menuitem', { name: 'Remove' })).toBeInTheDocument();
    });

    it('runs the action from the keyboard and closes, even when the call site prevents the default', async () => {
        const onRemove = vi.fn((event: any) => {
            // what the group form card and the groups table do
            event.stopPropagation();
            event.preventDefault();
        });
        render(<DeleteDropDown itemName="Volunteers" label="Delete" onDropDownItemClick={onRemove} />);
        keyboardOpen(screen.getByRole('button', { name: 'More actions for Volunteers' }));
        const item = await screen.findByRole('menuitem', { name: 'Delete' });

        await act(async () => void fireEvent.keyDown(item, { key: 'Enter' }));
        expect(onRemove).toHaveBeenCalledTimes(1);
        await waitFor(() => expect(screen.queryByRole('menu')).toBeNull());
    });

    it('does not open the card or row it sits in', async () => {
        const onCardClick = vi.fn();
        render(
            // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- stands in for a clickable card
            <div onClick={onCardClick}>
                <DeleteDropDown itemName="Job application" onDropDownItemClick={vi.fn()} />
            </div>
        );
        const trigger = screen.getByRole('button', { name: 'More actions for Job application' });
        fireEvent.pointerDown(trigger, { button: 0, ctrlKey: false });
        fireEvent.click(trigger);
        fireEvent.click(await screen.findByRole('menuitem', { name: 'Remove' }));
        expect(onCardClick).not.toHaveBeenCalled();
    });
});

describe('SettingRow', () => {
    it("names its switch by the row's title and describes it by the description", async () => {
        const { container } = render(
            <SettingRow title="Pin form" description="Pinned forms show first on your workspace page.">
                <Switch checked={false} onCheckedChange={vi.fn()} />
            </SettingRow>
        );
        const control = screen.getByRole('switch', { name: 'Pin form' });
        expect(control).toHaveAccessibleDescription('Pinned forms show first on your workspace page.');
        expect(await axeViolations(container)).toEqual([]);
    });

    it("keeps a switch's own name", () => {
        render(
            <SettingRow title="Pin form" description="Pinned forms show first.">
                <Switch aria-label="Pin this form" checked={false} onCheckedChange={vi.fn()} />
            </SettingRow>
        );
        expect(screen.getByRole('switch', { name: 'Pin this form' })).toBeInTheDocument();
    });
});

describe('the names in English and Dutch', () => {
    it('has every new name in both languages, with the item in it', () => {
        for (const locale of [commonEn, commonNl]) {
            expect(locale.A11Y.MORE_ACTIONS).toBeTruthy();
            expect(locale.A11Y.MORE_ACTIONS_FOR).toContain('{{name}}');
            expect(locale.A11Y.TURN_ON_OFF).toContain('{{name}}');
        }
        expect(commonNl.A11Y.MORE_ACTIONS_FOR).not.toBe(commonEn.A11Y.MORE_ACTIONS_FOR);
        expect(commonNl.A11Y.TURN_ON_OFF).not.toBe(commonEn.A11Y.TURN_ON_OFF);
    });
});
