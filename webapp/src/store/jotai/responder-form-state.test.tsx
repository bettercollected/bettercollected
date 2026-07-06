import React from 'react';

import { act, renderHook } from '@testing-library/react';
import { Provider } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// useResponderState reads the redux form only for nextField bounds — stub it.
vi.mock('@app/store/hooks', () => ({
    useAppSelector: () => ({ fields: [{ id: 's1', properties: { fields: [{ id: 'a' }, { id: 'b' }] } }, { id: 's2' }, { id: 's3' }] })
}));

import { useResponderState } from './responder-form-state';

const setup = () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => <Provider>{children}</Provider>;
    return renderHook(() => useResponderState(), { wrapper });
};

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

const settle = () => act(() => void vi.advanceTimersByTime(600));

describe('responder navigation history (jump-aware Back)', () => {
    it('starts on the welcome pseudo-slide with empty history', () => {
        const { result } = setup();
        expect(result.current.currentSlide).toBe(-1);
        expect(result.current.responderState.history).toEqual([]);
    });

    it('nextSlide advances linearly and records where it came from', () => {
        const { result } = setup();
        act(() => result.current.nextSlide());
        settle();
        expect(result.current.currentSlide).toBe(0);
        expect(result.current.responderState.history).toEqual([-1]);
    });

    it('goToSlide jumps anywhere and Back retraces the jump, not index-1', () => {
        const { result } = setup();
        act(() => result.current.nextSlide()); // welcome -> 0
        settle();
        act(() => result.current.goToSlide(2)); // jump 0 -> 2 (skipping 1)
        settle();
        expect(result.current.currentSlide).toBe(2);
        expect(result.current.responderState.history).toEqual([-1, 0]);

        act(() => result.current.previousSlide()); // back retraces to 0, not 1
        settle();
        expect(result.current.currentSlide).toBe(0);
        expect(result.current.responderState.history).toEqual([-1]);

        act(() => result.current.previousSlide());
        settle();
        expect(result.current.currentSlide).toBe(-1);
        expect(result.current.responderState.history).toEqual([]);
    });

    it('previousSlide falls back to index-1 when history is empty', () => {
        const { result } = setup();
        act(() => result.current.setResponderState({ ...result.current.responderState, currentSlide: 2, history: [] }));
        act(() => result.current.previousSlide());
        settle();
        expect(result.current.currentSlide).toBe(1);
    });

    it('returning to the welcome page clears history', () => {
        const { result } = setup();
        act(() => result.current.nextSlide());
        settle();
        act(() => result.current.setCurrentSlideToWelcomePage());
        expect(result.current.currentSlide).toBe(-1);
        expect(result.current.responderState.history).toEqual([]);
    });

    it('thank-you page is the -2 sentinel', () => {
        const { result } = setup();
        act(() => result.current.setCurrentSlideToThankyouPage());
        expect(result.current.currentSlide).toBe(-2);
    });

    it('resetResponderState restores the initial state', () => {
        const { result } = setup();
        act(() => result.current.goToSlide(2));
        settle();
        act(() => result.current.resetResponderState());
        expect(result.current.currentSlide).toBe(-1);
        expect(result.current.responderState.history).toEqual([]);
    });
});
