import { render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import EmbedReporter, { pageKindOf } from './embed-reporter';

const state = vi.hoisted(() => ({
    embed: { embedded: true, parentOrigin: 'https://www.example.org' as string | null },
    slide: -1,
    responderId: undefined as string | undefined,
    history: [] as number[],
    fields: [{}, {}, {}]
}));

vi.mock('@app/lib/embed/use-embed', () => ({ useEmbed: () => state.embed }));
vi.mock('@app/store/jotai/responder-form-state', () => ({
    useResponderState: () => ({ responderState: { currentSlide: state.slide, responderId: state.responderId, history: state.history } }),
    useShownSlide: () => state.slide
}));
vi.mock('@app/store/hooks', () => ({ useAppSelector: () => ({ fields: state.fields, title: 'A secret form title', description: 'and its text' }) }));
vi.mock('@app/store/forms/slice', () => ({ selectResponderForm: () => null }));

const posted = () => (window.parent.postMessage as ReturnType<typeof vi.fn>).mock.calls as Array<[Record<string, unknown>, string]>;

describe('EmbedReporter', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        state.embed = { embedded: true, parentOrigin: 'https://www.example.org' };
        state.slide = -1;
        state.responderId = undefined;
        state.history = [];
        state.fields = [{}, {}, {}];
        // jsdom's top window is its own parent: a stand-in makes this page "framed"
        Object.defineProperty(window, 'parent', { configurable: true, value: { postMessage: vi.fn() } });
    });
    afterEach(() => {
        vi.useRealTimers();
        vi.unstubAllGlobals();
        delete (window as { parent?: unknown }).parent;
        document.documentElement.removeAttribute('data-bc-embed');
        document.body.innerHTML = '';
    });

    it('names the kind of each page', () => {
        expect(pageKindOf(-1)).toBe('welcome');
        expect(pageKindOf(0)).toBe('question');
        expect(pageKindOf(7)).toBe('question');
        expect(pageKindOf(-2)).toBe('ending');
        expect(pageKindOf(-3)).toBe('review');
    });

    it('says loaded and which page it is on, to the parent origin only', () => {
        render(<EmbedReporter />);
        const calls = posted();
        expect(calls.map(([message]) => message.type)).toEqual(['loaded', 'page']);
        expect(calls[1][0]).toMatchObject({ kind: 'welcome', step: 0, total: 3 });
        expect(calls.every(([, origin]) => origin === 'https://www.example.org')).toBe(true);
        expect(document.documentElement.hasAttribute('data-bc-embed')).toBe(true);
    });

    it('reports a step counter on the way, then the ending, then submitted once', () => {
        const view = render(<EmbedReporter />);
        state.slide = 0;
        state.history = [-1];
        view.rerender(<EmbedReporter />);
        state.slide = 1;
        state.history = [-1, 0];
        view.rerender(<EmbedReporter />);
        state.slide = -2;
        state.responderId = 'response-id-1';
        view.rerender(<EmbedReporter />);
        view.rerender(<EmbedReporter />);
        const messages = posted().map(([message]) => message);
        expect(messages.filter((m) => m.type === 'page').map((m) => [m.kind, m.step])).toEqual([
            ['welcome', 0],
            ['question', 1],
            ['question', 2],
            ['ending', 2]
        ]);
        expect(messages.filter((m) => m.type === 'submitted')).toHaveLength(1);
    });

    it("does not repeat itself: loaded once, and a page only when it or the form's page count changed", () => {
        const view = render(<EmbedReporter />);
        view.rerender(<EmbedReporter />);
        view.rerender(<EmbedReporter />);
        expect(posted().map(([message]) => message.type)).toEqual(['loaded', 'page']);
        state.fields = [{}, {}, {}, {}];
        view.rerender(<EmbedReporter />);
        const pages = posted()
            .map(([message]) => message)
            .filter((message) => message.type === 'page');
        expect(pages.map((message) => message.total)).toEqual([3, 4]);
    });

    it('never puts an answer, a response id or a title in a message', () => {
        state.slide = -2;
        state.responderId = 'response-id-1';
        render(<EmbedReporter />);
        const text = JSON.stringify(posted().map(([message]) => message));
        expect(text).not.toContain('response-id-1');
        expect(text).not.toContain('secret form title');
        expect(text).not.toContain('responderId');
    });

    it('does not say submitted for an ending reached without a response', () => {
        state.slide = -2;
        render(<EmbedReporter />);
        expect(posted().map(([message]) => message.type)).not.toContain('submitted');
    });

    it('reports the height the page needs, once, and again only on a real change', () => {
        document.body.innerHTML = '<div data-slide="-1"><div data-radix-scroll-area-viewport><div id="content"></div></div></div>';
        const area = document.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement;
        Object.defineProperty(area, 'clientHeight', { value: 500, configurable: true });
        const content = document.getElementById('content') as HTMLElement;
        let contentHeight = 400;
        content.getBoundingClientRect = () => ({ height: contentHeight }) as DOMRect;
        Object.defineProperty(window, 'innerHeight', { value: 640, configurable: true });
        render(<EmbedReporter />);
        vi.advanceTimersByTime(600);
        const heights = () =>
            posted()
                .map(([m]) => m)
                .filter((m) => m.type === 'height')
                .map((m) => m.height);
        expect(heights()).toEqual([140 + 400]);
        contentHeight = 401;
        window.dispatchEvent(new Event('resize'));
        vi.advanceTimersByTime(100);
        expect(heights()).toEqual([540]);
        contentHeight = 700;
        window.dispatchEvent(new Event('resize'));
        vi.advanceTimersByTime(100);
        expect(heights()).toEqual([540, 840]);
    });

    it('waits for the page to settle: a size that is gone again within a moment is never reported', () => {
        document.body.innerHTML = '<div data-slide="-1"><div data-radix-scroll-area-viewport><div id="content"></div></div></div>';
        const area = document.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement;
        Object.defineProperty(area, 'clientHeight', { value: 500, configurable: true });
        let contentHeight = 1200;
        (document.getElementById('content') as HTMLElement).getBoundingClientRect = () => ({ height: contentHeight }) as DOMRect;
        Object.defineProperty(window, 'innerHeight', { value: 640, configurable: true });
        render(<EmbedReporter />);
        vi.advanceTimersByTime(40);
        contentHeight = 400;
        window.dispatchEvent(new Event('resize'));
        vi.advanceTimersByTime(600);
        const heights = posted()
            .map(([m]) => m)
            .filter((m) => m.type === 'height')
            .map((m) => m.height);
        expect(heights).toEqual([540]);
    });

    it('does nothing outside embed mode', () => {
        state.embed = { embedded: false, parentOrigin: null };
        render(<EmbedReporter />);
        vi.advanceTimersByTime(1000);
        expect(posted()).toEqual([]);
        expect(document.documentElement.hasAttribute('data-bc-embed')).toBe(false);
    });

    it('sends nothing without a parent origin, but still keeps links in a new tab', () => {
        state.embed = { embedded: true, parentOrigin: null };
        render(<EmbedReporter />);
        vi.advanceTimersByTime(1000);
        expect(posted()).toEqual([]);
        expect(document.documentElement.hasAttribute('data-bc-embed')).toBe(true);
    });

    it('leaves embed mode behind when it goes away', () => {
        const view = render(<EmbedReporter />);
        view.unmount();
        expect(document.documentElement.hasAttribute('data-bc-embed')).toBe(false);
    });
});
