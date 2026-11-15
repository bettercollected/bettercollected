import React from 'react';

import { act, render } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it } from 'vitest';

import { store } from '@app/store/store';
import { setAppTheme, setWorkspace } from '@app/store/workspaces/slice';

import AppThemeScope from './app-theme-scope';

const mount = (props: { workspaceId?: string; initial?: unknown } = {}) =>
    render(
        <ReduxProvider store={store}>
            <AppThemeScope workspaceId={props.workspaceId ?? 'ws-1'} initial={props.initial}>
                <p>page</p>
            </AppThemeScope>
        </ReduxProvider>
    );
const attribute = (container: HTMLElement) => container.querySelector('[data-app-theme]')?.getAttribute('data-app-theme');

beforeEach(() => {
    // no workspace in the store yet: what the server rendered is all there is
    act(() => {
        store.dispatch(setWorkspace({ id: '', title: '' }));
    });
});

describe('the app theme scope', () => {
    it('carries what the server read, so the first HTML is already in the right theme', () => {
        expect(attribute(mount({ initial: 'pigment' }).container)).toBe('pigment');
        expect(attribute(mount({ initial: 'daybreak' }).container)).toBe('daybreak');
    });

    it('is daybreak unless the member answer says pigment: no value, an unknown value or another type', () => {
        for (const initial of [undefined, null, '', 'sepia', 'PIGMENT', 'pigment ', 1, {}, ['pigment']]) {
            expect(attribute(mount({ initial }).container), JSON.stringify(initial)).toBe('daybreak');
        }
    });

    it('is a plain element that adds no box and keeps the page inside it', () => {
        const { container } = mount({ initial: 'pigment' });
        const scope = container.querySelector('[data-app-theme]') as HTMLElement;
        expect(scope.style.display).toBe('contents');
        expect(scope.textContent).toBe('page');
    });

    it('follows the workspace in the store once it is there, without a reload', () => {
        const { container } = mount({ initial: 'daybreak' });
        act(() => {
            store.dispatch(setWorkspace({ id: 'ws-1', appTheme: 'daybreak' }));
        });
        expect(attribute(container)).toBe('daybreak');
        act(() => {
            store.dispatch(setAppTheme({ workspaceId: 'ws-1', appTheme: 'pigment' }));
        });
        expect(attribute(container)).toBe('pigment');
        act(() => {
            store.dispatch(setAppTheme({ workspaceId: 'ws-1', appTheme: 'daybreak' }));
        });
        expect(attribute(container)).toBe('daybreak');
    });

    it('does not change on another workspace being in the store', () => {
        const { container } = mount({ initial: 'daybreak' });
        act(() => {
            store.dispatch(setWorkspace({ id: 'ws-2', appTheme: 'pigment' }));
        });
        expect(attribute(container)).toBe('daybreak');
        act(() => {
            store.dispatch(setAppTheme({ workspaceId: 'ws-1', appTheme: 'pigment' }));
        });
        // a change for a workspace that is not the one in the store changes nothing
        expect(store.getState().workspace.appTheme).toBe('pigment');
        expect(attribute(container)).toBe('daybreak');
    });

    it('keeps the theme when the workspace is replaced by an answer that has none (a rename, a logo)', () => {
        const { container } = mount({ initial: 'daybreak' });
        act(() => {
            store.dispatch(setWorkspace({ id: 'ws-1', appTheme: 'pigment', title: 'Acme' }));
        });
        act(() => {
            store.dispatch(setWorkspace({ id: 'ws-1', title: 'Acme, renamed' }));
        });
        expect(store.getState().workspace.title).toBe('Acme, renamed');
        expect(attribute(container)).toBe('pigment');
        // but not into another workspace
        act(() => {
            store.dispatch(setWorkspace({ id: 'ws-9', title: 'Other' }));
        });
        expect(store.getState().workspace.appTheme).toBeUndefined();
    });

    it('takes the server\'s newer value when the layout loads the workspace again', () => {
        mount({ initial: 'pigment' });
        act(() => {
            store.dispatch(setWorkspace({ id: 'ws-1', appTheme: 'pigment' }));
        });
        act(() => {
            // the switch was turned off on the server: members are served daybreak whatever is stored
            store.dispatch(setWorkspace({ id: 'ws-1', appTheme: 'daybreak' }));
        });
        expect(store.getState().workspace.appTheme).toBe('daybreak');
    });
});
