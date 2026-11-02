import { render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import EmbedReporter from './embed-reporter';

const state = vi.hoisted(() => ({
    embed: { embedded: true, parentOrigin: 'https://www.example.org' as string | null },
    switchOn: true as boolean | undefined,
    slide: -1,
    responderId: undefined as string | undefined,
    history: [] as number[]
}));

vi.mock('@app/lib/embed/use-embed', () => ({ useEmbed: () => state.embed }));
vi.mock('@app/store/jotai/responder-form-state', () => ({
    useResponderState: () => ({ responderState: { currentSlide: state.slide, responderId: state.responderId, history: state.history } }),
    useShownSlide: () => state.slide
}));
vi.mock('@app/store/hooks', () => ({ useAppSelector: () => ({ id: 'ws1' }) }));
vi.mock('@app/store/workspaces/slice', () => ({ selectWorkspace: () => ({}) }));
const policyCalls: Array<{ arg: unknown; skip: boolean | undefined }> = [];
vi.mock('@app/store/workspaces/embed-api', () => ({
    useGetEmbedPolicyQuery: (arg: unknown, options?: { skip?: boolean }) => {
        policyCalls.push({ arg, skip: options?.skip });
        return { data: options?.skip || state.switchOn === undefined ? undefined : { enabled: state.switchOn, origins: [] } };
    }
}));

const posted = () => (window.parent.postMessage as ReturnType<typeof vi.fn>).mock.calls as Array<[Record<string, unknown>, string]>;
const types = () => posted().map(([message]) => message.type);

function setUpPage(contentHeight: number) {
    document.body.innerHTML = '<div data-slide="-1"><div data-radix-scroll-area-viewport><div id="content"></div></div></div>';
    const area = document.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement;
    Object.defineProperty(area, 'clientHeight', { value: 500, configurable: true });
    const content = document.getElementById('content') as HTMLElement;
    const box = { height: contentHeight };
    content.getBoundingClientRect = () => ({ height: box.height }) as DOMRect;
    Object.defineProperty(window, 'innerHeight', { value: 640, configurable: true });
    return box;
}

describe('EmbedReporter', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        state.embed = { embedded: true, parentOrigin: 'https://www.example.org' };
        state.switchOn = true;
        state.slide = -1;
        state.responderId = undefined;
        state.history = [];
        policyCalls.length = 0;
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

    it('says loaded, to the parent origin only', () => {
        render(<EmbedReporter />);
        expect(types()).toEqual(['loaded']);
        expect(posted().every(([, origin]) => origin === 'https://www.example.org')).toBe(true);
        expect(document.documentElement.hasAttribute('data-bc-embed')).toBe(true);
    });

    it('says submitted once, when the ending comes with a response', () => {
        const view = render(<EmbedReporter />);
        state.slide = 0;
        view.rerender(<EmbedReporter />);
        state.slide = -2;
        state.responderId = 'response-id-1';
        view.rerender(<EmbedReporter />);
        view.rerender(<EmbedReporter />);
        expect(types().filter((type) => type === 'submitted')).toHaveLength(1);
        expect(JSON.stringify(posted())).not.toContain('response-id-1');
    });

    it('does not say submitted for an ending reached without a response', () => {
        state.slide = -2;
        render(<EmbedReporter />);
        expect(types()).not.toContain('submitted');
    });

    it('sends only loaded, height and submitted, and each with fixed fields: no page, step, count, id or text', () => {
        const box = setUpPage(400);
        const view = render(<EmbedReporter />);
        vi.advanceTimersByTime(600);
        for (const slide of [0, 1, -3, -2]) {
            state.slide = slide;
            state.responderId = slide === -2 ? 'response-id-1' : undefined;
            box.height += 100;
            view.rerender(<EmbedReporter />);
            vi.advanceTimersByTime(600);
        }
        const messages = posted().map(([message]) => message);
        expect(new Set(messages.map((message) => message.type))).toEqual(new Set(['loaded', 'height', 'submitted']));
        for (const message of messages) {
            const keys = Object.keys(message).filter((key) => !['source', 'v', 'type'].includes(key));
            expect(keys).toEqual(message.type === 'height' ? ['height'] : []);
        }
        expect(JSON.stringify(messages)).not.toMatch(/page|step|total|kind|response-id-1|responderId/);
    });

    it("does not tell a branching form's paths apart: the same messages whichever pages were seen", () => {
        const run = (history: number[]) => {
            posted().length = 0;
            (window.parent.postMessage as ReturnType<typeof vi.fn>).mockClear();
            state.slide = -1;
            state.responderId = undefined;
            state.history = [];
            const view = render(<EmbedReporter />);
            // answer "no" on the first page: the jump skips two pages (history 3 long) or not (history 1 long)
            state.history = history;
            state.slide = -2;
            state.responderId = 'r1';
            view.rerender(<EmbedReporter />);
            const sequence = posted().map(([message]) => message);
            view.unmount();
            return sequence;
        };
        const longPath = run([-1, 0, 1, 2]);
        const shortPath = run([-1, 0]);
        expect(longPath).toEqual(shortPath);
        expect(longPath.map((message) => message.type)).toEqual(['loaded', 'submitted']);
    });

    it('reports the height the page needs in steps of 40 px, once, and again only on a real change', () => {
        const box = setUpPage(400);
        render(<EmbedReporter />);
        vi.advanceTimersByTime(600);
        const heights = () =>
            posted()
                .map(([m]) => m)
                .filter((m) => m.type === 'height')
                .map((m) => m.height);
        // 140 around the page and 400 of content is 540: reported as 560
        expect(heights()).toEqual([560]);
        box.height = 401;
        window.dispatchEvent(new Event('resize'));
        vi.advanceTimersByTime(100);
        expect(heights()).toEqual([560]);
        box.height = 700;
        window.dispatchEvent(new Event('resize'));
        vi.advanceTimersByTime(100);
        expect(heights()).toEqual([560, 840]);
    });

    it('waits for the page to settle: a size that is gone again within a moment is never reported', () => {
        const box = setUpPage(1200);
        render(<EmbedReporter />);
        vi.advanceTimersByTime(40);
        box.height = 400;
        window.dispatchEvent(new Event('resize'));
        vi.advanceTimersByTime(600);
        const heights = posted()
            .map(([m]) => m)
            .filter((m) => m.type === 'height')
            .map((m) => m.height);
        expect(heights).toEqual([560]);
    });

    describe('while the server has embedding switched off', () => {
        it('sends nothing, even in embed mode with a parent, but still keeps links in a new tab', () => {
            state.switchOn = false;
            setUpPage(400);
            const view = render(<EmbedReporter />);
            state.slide = -2;
            state.responderId = 'r1';
            view.rerender(<EmbedReporter />);
            vi.advanceTimersByTime(1000);
            expect(posted()).toEqual([]);
            expect(document.documentElement.hasAttribute('data-bc-embed')).toBe(true);
        });

        it('sends nothing before the policy has arrived, or when it cannot be read', () => {
            state.switchOn = undefined;
            setUpPage(400);
            render(<EmbedReporter />);
            vi.advanceTimersByTime(1000);
            expect(posted()).toEqual([]);
        });

        it('starts to send once the policy says it is on', () => {
            state.switchOn = undefined;
            const view = render(<EmbedReporter />);
            expect(posted()).toEqual([]);
            state.switchOn = true;
            view.rerender(<EmbedReporter />);
            expect(types()).toEqual(['loaded']);
        });
    });

    it('asks for the policy of this workspace only in embed mode with a parent to tell', () => {
        render(<EmbedReporter />);
        expect(policyCalls[0]).toEqual({ arg: 'ws1', skip: false });
        policyCalls.length = 0;
        state.embed = { embedded: false, parentOrigin: null };
        render(<EmbedReporter />);
        expect(policyCalls[0].skip).toBe(true);
        policyCalls.length = 0;
        state.embed = { embedded: true, parentOrigin: null };
        render(<EmbedReporter />);
        expect(policyCalls[0].skip).toBe(true);
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
