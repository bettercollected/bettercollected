// The "Restricted" chip: text and a lock, in the form's bar (from the form's access answer) and on a dashboard card
// (from the form's own `access`), only while the server has form-level access on, and without a request when off.
import React from 'react';

import { render, screen } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';

import { CardRestrictedChip, FormBarRestrictedChip, RestrictedChip } from './restricted-chip';

import commonNl from '../../../../public/locales/nl/common.json';

const served = vi.hoisted(() => ({ enabled: true, access: { data: undefined as any }, queries: [] as Array<{ args: any; options: any }> }));

vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ formAccessEnabled: served.enabled }) }));
vi.mock('@app/store/workspaces/form-access-api', async (original) => ({
    ...((await original()) as object),
    useGetFormAccessQuery: (args: any, options: any) => {
        served.queries.push({ args, options });
        return options?.skip ? { data: undefined } : served.access;
    }
}));

const wrap = (node: React.ReactNode) => render(<ReduxProvider store={store}>{node}</ReduxProvider>);

describe('the Restricted chip', () => {
    beforeAll(() => {
        i18n.addResourceBundle('nl', 'common', commonNl, true, true);
    });

    afterEach(async () => {
        await i18n.changeLanguage('en');
    });

    beforeEach(() => {
        served.enabled = true;
        served.access = { data: { enabled: true, restricted: true, canManage: true } };
        served.queries = [];
        store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'voorbeeld' } as any));
    });

    it('says Restricted in words, with the meaning on hover, and a lock that screen readers skip', () => {
        const { container } = wrap(<RestrictedChip />);
        const chip = screen.getByTestId('restricted-chip');
        expect(chip.textContent).toBe('Restricted');
        expect(chip).toHaveAttribute('title', 'Only selected people and teams can open this form in the dashboard');
        expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    });

    it('is Beperkt in Dutch', async () => {
        await i18n.changeLanguage('nl');
        wrap(<RestrictedChip />);
        expect(screen.getByTestId('restricted-chip').textContent).toBe('Beperkt');
    });

    describe('in the form bar', () => {
        it('shows for a restricted form, asking the form\'s access once', () => {
            wrap(<FormBarRestrictedChip form={{ formId: 'f1' } as any} />);
            expect(screen.getByTestId('restricted-chip')).toBeInTheDocument();
            expect(served.queries.at(-1)?.args).toEqual({ workspaceId: 'ws-1', formId: 'f1' });
            expect(served.queries.at(-1)?.options.skip).toBe(false);
        });

        it('does not show for an open form', () => {
            served.access = { data: { enabled: true, restricted: false } };
            wrap(<FormBarRestrictedChip form={{ formId: 'f1' } as any} />);
            expect(screen.queryByTestId('restricted-chip')).toBeNull();
        });

        it('shows nothing and does not ask while the switch is off, or before the form is known', () => {
            served.enabled = false;
            const off = wrap(<FormBarRestrictedChip form={{ formId: 'f1' } as any} />);
            expect(screen.queryByTestId('restricted-chip')).toBeNull();
            expect(served.queries.every((query) => query.options.skip === true)).toBe(true);
            off.unmount();
            served.enabled = true;
            served.queries = [];
            wrap(<FormBarRestrictedChip form={undefined} />);
            expect(screen.queryByTestId('restricted-chip')).toBeNull();
            expect(served.queries.every((query) => query.options.skip === true)).toBe(true);
        });

        it('shows nothing when the server says it is off', () => {
            served.access = { data: { enabled: false } };
            wrap(<FormBarRestrictedChip form={{ formId: 'f1' } as any} />);
            expect(screen.queryByTestId('restricted-chip')).toBeNull();
        });
    });

    describe('on a dashboard card', () => {
        it('shows from the form\'s own access block and asks for nothing', () => {
            wrap(<CardRestrictedChip form={{ formId: 'f1', access: { restricted: true } } as any} />);
            expect(screen.getByTestId('restricted-chip')).toBeInTheDocument();
            expect(served.queries).toEqual([]);
        });

        it('does not show for an open form, a form without the block, or while the switch is off', () => {
            const open = wrap(<CardRestrictedChip form={{ formId: 'f1', access: { restricted: false } } as any} />);
            expect(screen.queryByTestId('restricted-chip')).toBeNull();
            open.unmount();
            const bare = wrap(<CardRestrictedChip form={{ formId: 'f1' } as any} />);
            expect(screen.queryByTestId('restricted-chip')).toBeNull();
            bare.unmount();
            served.enabled = false;
            wrap(<CardRestrictedChip form={{ formId: 'f1', access: { restricted: true } } as any} />);
            expect(screen.queryByTestId('restricted-chip')).toBeNull();
        });
    });

    it('has no accessibility violations', async () => {
        const { container } = wrap(<RestrictedChip />);
        expect(await axeViolations(container)).toEqual([]);
    });
});
