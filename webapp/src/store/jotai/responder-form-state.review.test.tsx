import React from 'react';

import { act, renderHook } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { store } from '@app/store/store';

import { useResponderState } from './responder-form-state';

const wrapper = ({ children }: { children: React.ReactNode }) => (
    <ReduxProvider store={store}>
        <Provider>{children}</Provider>
    </ReduxProvider>
);

describe('the respondent journey state with a review page', () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    it('forgets the page it left once the transition is over', () => {
        const { result } = renderHook(() => useResponderState(), { wrapper });
        act(() => result.current.goToSlide(1));
        expect(result.current.currentSlide).toBe(1);
        expect(result.current.prevActiveSlide).toBe(-1);
        act(() => void vi.advanceTimersByTime(500));
        expect(result.current.prevActiveSlide).toBe(1);
    });

    it('a move made during the transition is not undone when it ends', () => {
        const { result } = renderHook(() => useResponderState(), { wrapper });
        act(() => result.current.goToSlide(2));
        // the respondent goes on at once (to the review) before the 500 ms are up
        act(() => result.current.goToReview());
        expect(result.current.currentSlide).toBe(-3);
        act(() => void vi.advanceTimersByTime(600));
        expect(result.current.currentSlide).toBe(-3);
        expect(result.current.responderState.history).toEqual([2]);
    });

    it('submitting within the transition (the ending) is not undone when it ends', () => {
        const { result } = renderHook(() => useResponderState(), { wrapper });
        act(() => result.current.goToSlide(2));
        // the respondent sends the form at once: the ending shows, and stays
        act(() => result.current.setCurrentSlideToThankyouPage('end'));
        expect(result.current.currentSlide).toBe(-2);
        act(() => void vi.advanceTimersByTime(600));
        expect(result.current.currentSlide).toBe(-2);
        expect(result.current.endingId).toBe('end');
    });

    it('Back during a transition is not undone either', () => {
        const { result } = renderHook(() => useResponderState(), { wrapper });
        act(() => result.current.goToSlide(1));
        act(() => void vi.advanceTimersByTime(500));
        act(() => result.current.goToSlide(2));
        act(() => result.current.previousSlide());
        act(() => void vi.advanceTimersByTime(600));
        expect(result.current.currentSlide).toBe(1);
    });

    it('keeps the reviewed path only for a page on it', () => {
        const { result } = renderHook(() => useResponderState(), { wrapper });
        act(() => result.current.goToSlide(0));
        act(() => result.current.goToSlide(1));
        act(() => result.current.goToSlide(2));
        act(() => result.current.goToReview());
        act(() => result.current.editFromReview(1));
        expect(result.current.responderState.reviewPath).toEqual([0, 1, 2]);
        act(() => result.current.goToSlide(2));
        expect(result.current.responderState.reviewPath).toEqual([0, 1, 2]);
        act(() => result.current.goToSlide(7));
        expect(result.current.responderState.reviewPath).toBeUndefined();
    });
});
