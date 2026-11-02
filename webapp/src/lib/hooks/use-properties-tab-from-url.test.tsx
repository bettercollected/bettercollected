import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { propertiesTabFromParam, usePropertiesTab } from '@app/store/jotai/properties-tab';

import { usePropertiesTabFromUrl } from './use-properties-tab-from-url';

const url = vi.hoisted(() => ({ query: '' }));
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams(url.query) }));

const open = () => renderHook(() => ({ from: usePropertiesTabFromUrl(), tab: usePropertiesTab() }));

describe('propertiesTabFromParam', () => {
    it('knows the tabs a link may open, and nothing else', () => {
        expect(propertiesTabFromParam('form')).toBe('form');
        expect(propertiesTabFromParam('page')).toBe('page');
        expect(propertiesTabFromParam('design')).toBe('design');
        for (const other of ['ai', 'Form', '', 'x', null, undefined]) expect(propertiesTabFromParam(other as any)).toBeNull();
    });
});

describe('the builder opening on a tab from the address', () => {
    beforeEach(() => {
        // each test starts on the page tab, whatever the one before left
        url.query = 'tab=page';
        open().unmount();
    });

    it('opens the Form tab for ?tab=form', () => {
        url.query = 'tab=form';
        const { result } = open();
        expect(result.current.tab.propertiesTab).toBe('form');
    });

    it('opens the Design tab for ?tab=design', () => {
        url.query = 'tab=design';
        expect(open().result.current.tab.propertiesTab).toBe('design');
    });

    it('leaves the drawer on the page tab without a tab, and for an unknown one or the AI tab', () => {
        for (const query of ['', 'tab=nonsense', 'tab=ai', 'showTitle=true']) {
            url.query = query;
            expect(open().result.current.tab.propertiesTab).toBe('page');
        }
    });
});
