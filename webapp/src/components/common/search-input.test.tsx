import React, { useState } from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import I18nProvider from '@app/shared/hocs/i18n-provider';

import SearchInput from './search-input';

// Like most callers: a new handler function on every render of the parent.
const Parent = ({ onSearch }: { onSearch: (value: string) => void }) => {
    const [renders, setRenders] = useState(0);
    return (
        <I18nProvider>
            <button onClick={() => setRenders(renders + 1)}>rerender</button>
            <SearchInput placeholder="Search" handleSearch={(event: any) => onSearch(`${event.target.value}|render${renders}`)} />
        </I18nProvider>
    );
};

describe('SearchInput debounce', () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('fires once with the last text, even when the parent re-renders with a new handler mid-debounce', () => {
        const onSearch = vi.fn();
        render(<Parent onSearch={onSearch} />);
        const input = screen.getByPlaceholderText('Search');
        fireEvent.change(input, { target: { value: 'ab' } });
        act(() => {
            vi.advanceTimersByTime(200);
        });
        fireEvent.click(screen.getByText('rerender')); // new handler identity
        fireEvent.change(input, { target: { value: 'abc' } });
        act(() => {
            vi.advanceTimersByTime(200);
        });
        fireEvent.click(screen.getByText('rerender'));
        expect(onSearch).not.toHaveBeenCalled();
        act(() => {
            vi.advanceTimersByTime(600);
        });
        expect(onSearch).toHaveBeenCalledTimes(1);
        // the latest handler (second re-render) receives the last text
        expect(onSearch).toHaveBeenCalledWith('abc|render2');
    });

    it('does not fire after it has been removed from the page', () => {
        const onSearch = vi.fn();
        const { unmount } = render(<Parent onSearch={onSearch} />);
        fireEvent.change(screen.getByPlaceholderText('Search'), { target: { value: 'x' } });
        unmount();
        act(() => {
            vi.advanceTimersByTime(1000);
        });
        expect(onSearch).not.toHaveBeenCalled();
    });
});
