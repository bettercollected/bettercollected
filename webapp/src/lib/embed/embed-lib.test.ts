import { describe, expect, it, vi } from 'vitest';

import { MAX_FRAME_HEIGHT, MIN_FRAME_HEIGHT, heightChanged, measureNeededHeight, neededHeight } from './embed-height';
import { guardLinks, opensOutside } from './embed-links';
import { EMBED_SOURCE, EMBED_VERSION, heightMessage, loadedMessage, postToParent, submittedMessage } from './embed-messages';
import { asOrigin, readEmbedContext } from './embed-params';

describe('embed address', () => {
    it('is embed mode only for embed=1', () => {
        expect(readEmbedContext('')).toEqual({ embedded: false, parentOrigin: null });
        expect(readEmbedContext('?embed=0&parent=https://a.example.org')).toEqual({ embedded: false, parentOrigin: null });
        expect(readEmbedContext('?embed=true')).toEqual({ embedded: false, parentOrigin: null });
        expect(readEmbedContext('?embed=1')).toEqual({ embedded: true, parentOrigin: null });
        expect(readEmbedContext('?lang=nl&embed=1&parent=https%3A%2F%2Fwww.example.org')).toEqual({ embedded: true, parentOrigin: 'https://www.example.org' });
    });

    it.each([
        ['https://www.example.org', 'https://www.example.org'],
        ['http://localhost:3000', 'http://localhost:3000'],
        ['https://www.example.org/', null],
        ['https://www.example.org/path', null],
        ['https://www.example.org?x=1', null],
        ['https://user:pw@www.example.org', null],
        ['javascript:alert(1)', null],
        ['*', null],
        ['null', null],
        ['', null],
        [null, null]
    ])('takes %s as the parent origin: %s', (value, expected) => {
        expect(asOrigin(value)).toBe(expected);
    });

    it('gives an embed page without a usable parent no one to talk to', () => {
        expect(readEmbedContext('?embed=1&parent=*')).toEqual({ embedded: true, parentOrigin: null });
        expect(readEmbedContext('?embed=1&parent=https://a.example.org/x')).toEqual({ embedded: true, parentOrigin: null });
    });
});

describe('embed messages', () => {
    it('are exactly the lifecycle shapes of protocol v1', () => {
        const base = { source: EMBED_SOURCE, v: EMBED_VERSION };
        expect(EMBED_SOURCE).toBe('bettercollected-form');
        expect(EMBED_VERSION).toBe(1);
        expect(loadedMessage()).toEqual({ ...base, type: 'loaded' });
        expect(heightMessage(640)).toEqual({ ...base, type: 'height', height: 640 });
        expect(submittedMessage()).toEqual({ ...base, type: 'submitted' });
    });

    it('carry no answer, id or text: every key of every message is a known one', () => {
        const allowed = new Set(['source', 'v', 'type', 'height']);
        for (const message of [loadedMessage(), heightMessage(300), submittedMessage()]) {
            for (const key of Object.keys(message)) expect(allowed.has(key)).toBe(true);
            for (const value of Object.values(message)) expect(['string', 'number']).toContain(typeof value);
        }
    });

    describe('postToParent', () => {
        const framed = () => {
            const post = vi.fn();
            const win = { parent: { postMessage: post } } as unknown as Window;
            return { win, post };
        };

        it('addresses exactly the parent origin, never "*"', () => {
            const { win, post } = framed();
            expect(postToParent(loadedMessage(), 'https://www.example.org', win)).toBe(true);
            expect(post).toHaveBeenCalledWith(loadedMessage(), 'https://www.example.org');
            expect(post.mock.calls[0][1]).not.toBe('*');
        });

        it('sends nothing without a parent origin', () => {
            const { win, post } = framed();
            expect(postToParent(loadedMessage(), null, win)).toBe(false);
            expect(postToParent(loadedMessage(), '', win)).toBe(false);
            expect(post).not.toHaveBeenCalled();
        });

        it('sends nothing from a page that is not in a frame', () => {
            const post = vi.fn();
            const win = { postMessage: post } as unknown as Window & { parent: Window };
            win.parent = win;
            expect(postToParent(loadedMessage(), 'https://www.example.org', win)).toBe(false);
            expect(post).not.toHaveBeenCalled();
        });
    });
});

describe('embed height', () => {
    it('is what surrounds the scroll area plus the content, within bounds, in steps of 40 px', () => {
        // a 700 px frame, a 560 px scroll area (the strips take 140), 900 px of content
        expect(neededHeight({ frameHeight: 700, scrollAreaHeight: 560, contentHeight: 900 })).toBe(1040);
        expect(neededHeight({ frameHeight: 700, scrollAreaHeight: 560, contentHeight: 300.2 })).toBe(480);
        expect(neededHeight({ frameHeight: 700, scrollAreaHeight: 560, contentHeight: 10 })).toBe(MIN_FRAME_HEIGHT);
        expect(neededHeight({ frameHeight: 700, scrollAreaHeight: 560, contentHeight: 99999 })).toBe(MAX_FRAME_HEIGHT);
    });

    it('does not change when the frame follows it (no resize loop)', () => {
        const content = 420;
        const chrome = 140;
        let frame = 900;
        const heights: number[] = [];
        for (let i = 0; i < 4; i++) {
            heights.push((frame = neededHeight({ frameHeight: frame, scrollAreaHeight: frame - chrome, contentHeight: content })));
        }
        expect(new Set(heights).size).toBe(1);
        expect(heights[0]).toBe(560);
    });

    it('ignores changes below the tolerance', () => {
        expect(heightChanged(null, 500)).toBe(true);
        expect(heightChanged(500, 501)).toBe(false);
        expect(heightChanged(500, 502)).toBe(true);
        expect(heightChanged(500, 480)).toBe(true);
    });

    it('measures the scroll area of the page on screen only', () => {
        document.body.innerHTML = `
            <div data-slide="1"><div data-radix-scroll-area-viewport><div id="old"></div></div></div>
            <div data-slide="2"><div data-radix-scroll-area-viewport><div id="new"></div></div></div>`;
        const area = (slide: number) => document.querySelector<HTMLElement>(`[data-slide="${slide}"] [data-radix-scroll-area-viewport]`) as HTMLElement;
        Object.defineProperty(area(2), 'clientHeight', { value: 500, configurable: true });
        Object.defineProperty(area(1), 'clientHeight', { value: 100 });
        (document.getElementById('new') as HTMLElement).getBoundingClientRect = () => ({ height: 640 }) as DOMRect;
        expect(measureNeededHeight(document, 600, 2)).toBe(760);
        expect(measureNeededHeight(document, 600, 9)).toBeNull();
        Object.defineProperty(area(2), 'clientHeight', { value: 0, configurable: true });
        expect(measureNeededHeight(document, 600, 2)).toBeNull();
    });
});

describe('embed links', () => {
    const here = { origin: 'https://forms.example.org', pathname: '/acme/forms/contact' };
    const link = (href: string, target = '') => ({ href: new URL(href, 'https://forms.example.org/acme/forms/contact').href, target });

    it('opens outside for a link that leaves the form page', () => {
        expect(opensOutside(link('/login?type=responder'), here)).toBe(true);
        expect(opensOutside(link('/acme/submissions/123'), here)).toBe(true);
        expect(opensOutside(link('https://other.example.net/privacy'), here)).toBe(true);
    });

    it('leaves in-page links, links with a target, and non-web links alone', () => {
        expect(opensOutside(link('#resume=token'), here)).toBe(false);
        expect(opensOutside(link('/acme/forms/contact?lang=nl'), here)).toBe(false);
        expect(opensOutside(link('https://other.example.net/privacy', '_blank'), here)).toBe(false);
        expect(opensOutside({ href: 'mailto:team@example.org', target: '' }, here)).toBe(false);
        expect(opensOutside({ href: 'tel:+31000', target: '' }, here)).toBe(false);
        expect(opensOutside({ href: 'not a url', target: '' }, here)).toBe(false);
    });

    describe('guardLinks', () => {
        const setup = () => {
            document.body.innerHTML = '<a id="out" href="/login"><span id="inner">Sign in</span></a><a id="same" href="#top">Top</a><a id="blank" href="https://x.example.net" target="_blank">x</a>';
            const open = vi.fn();
            const win = { location: { origin: window.location.origin, pathname: window.location.pathname }, open } as unknown as Window;
            const stop = guardLinks(document, win);
            return { open, stop };
        };
        const click = (id: string, init: MouseEventInit = {}) => {
            const event = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0, ...init });
            (document.getElementById(id) as HTMLElement).dispatchEvent(event);
            return event;
        };

        it('sends a leaving link to a new tab without opener or referrer, and stops the page navigating', () => {
            const { open, stop } = setup();
            const event = click('inner');
            expect(event.defaultPrevented).toBe(true);
            expect(open).toHaveBeenCalledWith(new URL('/login', window.location.href).href, '_blank', 'noopener,noreferrer');
            stop();
        });

        it('leaves in-page links, targeted links and modified clicks to the browser', () => {
            const { open, stop } = setup();
            expect(click('same').defaultPrevented).toBe(false);
            expect(click('blank').defaultPrevented).toBe(false);
            expect(click('out', { ctrlKey: true }).defaultPrevented).toBe(false);
            expect(click('out', { button: 1 }).defaultPrevented).toBe(false);
            expect(open).not.toHaveBeenCalled();
            stop();
        });

        it('stops when removed', () => {
            const { open, stop } = setup();
            stop();
            expect(click('out').defaultPrevented).toBe(false);
            expect(open).not.toHaveBeenCalled();
        });
    });
});
