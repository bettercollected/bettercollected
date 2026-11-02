import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// The script as a host page would load it: evaluated in the page's global scope, once per test.
import source from '../../../public/embed/v1.js?raw';

const FORM = 'https://forms.example.org/acme/forms/contact';
const FORM_ORIGIN = 'https://forms.example.org';

declare global {
    interface Window {
        BetterCollectedEmbed?: { version: number; scan: (root?: ParentNode) => void; on: (type: string, handler: (detail: any, element: Element) => void) => () => void };
    }
}

function load() {
    delete window.BetterCollectedEmbed;
    (0, eval)(source);
}

function place(attributes: Record<string, string> = {}) {
    const element = document.createElement('div');
    element.setAttribute('data-bc-form', FORM);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    document.body.appendChild(element);
    return element;
}

const frameOf = (element: Element) => element.querySelector('iframe') as HTMLIFrameElement;

function send(frame: HTMLIFrameElement | null, data: unknown, origin = FORM_ORIGIN) {
    window.dispatchEvent(new MessageEvent('message', { data, origin, source: frame ? frame.contentWindow : null }));
}

const message = (type: string, rest: Record<string, unknown> = {}) => ({ source: 'bettercollected-form', v: 1, type, ...rest });

describe('embed.js', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
    });
    afterEach(() => {
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });

    describe('the frame', () => {
        it('puts the form in one frame with its name, the embed flag and the host origin', () => {
            const element = place({ 'data-bc-title': 'Contact form', 'data-bc-lang': 'nl' });
            load();
            const frame = frameOf(element);
            expect(element.querySelectorAll('iframe')).toHaveLength(1);
            const src = new URL(frame.getAttribute('src') as string);
            expect(src.origin + src.pathname).toBe(FORM);
            expect(src.searchParams.get('embed')).toBe('1');
            expect(src.searchParams.get('parent')).toBe(window.location.origin);
            expect(src.searchParams.get('lang')).toBe('nl');
            expect(frame.getAttribute('title')).toBe('Contact form');
            // no feature is handed to the form, and only this site's origin goes along as referrer
            expect(frame.getAttribute('allow')).toBe('');
            expect(frame.getAttribute('referrerpolicy')).toBe('origin');
            expect(frame.getAttribute('loading')).toBe('lazy');
        });

        it('names the frame "Form" without a title and keeps the address\'s own query', () => {
            const element = place();
            element.setAttribute('data-bc-form', `${FORM}?field_source=newsletter`);
            load();
            const src = new URL(frameOf(element).getAttribute('src') as string);
            expect(frameOf(element).getAttribute('title')).toBe('Form');
            expect(src.searchParams.get('field_source')).toBe('newsletter');
            expect(src.searchParams.get('lang')).toBeNull();
        });

        it('starts at the minimum height (clamped) and takes the theme hint as the colour scheme only', () => {
            const element = place({ 'data-bc-min-height': '600', 'data-bc-theme': 'dark' });
            const tiny = place({ 'data-bc-min-height': '5' });
            const huge = place({ 'data-bc-min-height': '999999' });
            const plain = place();
            const odd = place({ 'data-bc-theme': 'purple' });
            load();
            expect(frameOf(element).style.height).toBe('600px');
            expect(frameOf(element).style.colorScheme).toBe('dark');
            expect(frameOf(tiny).style.height).toBe('240px');
            expect(frameOf(huge).style.height).toBe('4000px');
            expect(frameOf(plain).style.height).toBe('480px');
            expect(frameOf(odd).style.colorScheme).toBe('');
        });

        it('animates the height unless the visitor prefers reduced motion', () => {
            const match = (reduce: boolean) => vi.stubGlobal('matchMedia', (query: string) => ({ matches: reduce && query.includes('reduce'), media: query }) as MediaQueryList);
            match(false);
            const calm = place();
            load();
            expect(frameOf(calm).style.transition).toContain('height');
            document.body.innerHTML = '';
            match(true);
            const still = place();
            load();
            expect(frameOf(still).style.transition).toBe('');
        });

        it.each([
            ['http://forms.example.org/a', 'a plain http address'],
            ['javascript:alert(1)', 'a script address'],
            ['data:text/html,<p>x</p>', 'a data address'],
            ['//forms.example.org/a', 'a scheme-less address'],
            ['/acme/forms/contact', 'a relative address'],
            ['https://user:secret@forms.example.org/a', 'an address with credentials'],
            ['https://forms.example.org/a#resume=token', 'an address with a fragment'],
            ['', 'an empty address']
        ])('refuses %s (%s)', (address) => {
            const element = place();
            element.setAttribute('data-bc-form', address);
            load();
            expect(frameOf(element)).toBeNull();
            expect(element.getAttribute('data-bc-error')).toBe('address');
        });

        it('allows http for names under .localhost too, but not for look-alikes', () => {
        const element = place();
        element.setAttribute('data-bc-form', 'http://forms.localhost:3243/acme/forms/contact');
        const lookalike = place();
        lookalike.setAttribute('data-bc-form', 'http://forms.localhost.example.org/acme/forms/contact');
        const other = place();
        other.setAttribute('data-bc-form', 'http://evil-localhost/acme/forms/contact');
        load();
        expect(new URL(frameOf(element).getAttribute('src') as string).origin).toBe('http://forms.localhost:3243');
        expect(frameOf(lookalike)).toBeNull();
        expect(frameOf(other)).toBeNull();
    });

    it('allows http for localhost, to try it', () => {
            const element = place();
            element.setAttribute('data-bc-form', 'http://localhost:3001/acme/forms/contact');
            load();
            expect(new URL(frameOf(element).getAttribute('src') as string).origin).toBe('http://localhost:3001');
        });

        it('mounts a placeholder once, also when the script is loaded twice or scanned again', () => {
            const element = place();
            load();
            const first = window.BetterCollectedEmbed;
            window.BetterCollectedEmbed?.scan();
            (0, eval)(source);
            expect(window.BetterCollectedEmbed).toBe(first);
            expect(element.querySelectorAll('iframe')).toHaveLength(1);
            const later = place();
            first?.scan();
            expect(later.querySelectorAll('iframe')).toHaveLength(1);
            expect(first?.version).toBe(1);
        });

        it('scans only the part of the page it is given', () => {
            load();
            const inside = document.createElement('section');
            const innerPlaceholder = document.createElement('div');
            innerPlaceholder.setAttribute('data-bc-form', FORM);
            inside.appendChild(innerPlaceholder);
            document.body.appendChild(inside);
            const outside = place();
            window.BetterCollectedEmbed?.scan(inside);
            expect(frameOf(innerPlaceholder)).not.toBeNull();
            expect(frameOf(outside)).toBeNull();
        });
    });

    describe('messages from the form', () => {
        it('sets the height of the frame that sent it, within bounds and rounded', () => {
            const a = place();
            const b = place();
            load();
            send(frameOf(a), message('height', { height: 733.4 }));
            expect(frameOf(a).style.height).toBe('733px');
            expect(frameOf(b).style.height).toBe('480px');
            send(frameOf(a), message('height', { height: 99999 }));
            expect(frameOf(a).style.height).toBe('4000px');
            send(frameOf(a), message('height', { height: 3 }));
            expect(frameOf(a).style.height).toBe('240px');
        });

        it('reports loaded, height and submitted as DOM events with exactly the known data', () => {
            const element = place();
            load();
            const seen: Array<[string, unknown]> = [];
            for (const type of ['loaded', 'height', 'submitted']) {
                element.addEventListener(`bc-form:${type}`, (event) => seen.push([type, (event as CustomEvent).detail]));
            }
            send(frameOf(element), message('loaded', { extra: 'dropped' }));
            send(frameOf(element), message('submitted', { responseId: 'r1', answers: { a: 1 } }));
            send(frameOf(element), message('height', { height: 500, title: 'Form title' }));
            expect(seen).toEqual([
                ['loaded', { type: 'loaded' }],
                ['submitted', { type: 'submitted' }],
                ['height', { type: 'height', height: 500 }]
            ]);
            expect(element.hasAttribute('data-bc-loaded')).toBe(true);
        });

        it('calls handlers registered with on(), until they are removed', () => {
            const element = place();
            load();
            const handler = vi.fn();
            const off = window.BetterCollectedEmbed?.on('submitted', handler) as () => void;
            send(frameOf(element), message('submitted'));
            expect(handler).toHaveBeenCalledTimes(1);
            expect(handler).toHaveBeenCalledWith({ type: 'submitted' }, element);
            off();
            send(frameOf(element), message('submitted'));
            expect(handler).toHaveBeenCalledTimes(1);
        });

        it('keeps working when a host handler throws', () => {
            const element = place();
            load();
            window.BetterCollectedEmbed?.on('submitted', () => {
                throw new Error('host bug');
            });
            const later = vi.fn();
            window.BetterCollectedEmbed?.on('submitted', later);
            send(frameOf(element), message('submitted'));
            expect(later).toHaveBeenCalledTimes(1);
        });

        describe('refuses', () => {
            let element: HTMLElement;
            let seen: unknown[];
            beforeEach(() => {
                element = place();
                load();
                seen = [];
                for (const type of ['loaded', 'height', 'submitted']) element.addEventListener(`bc-form:${type}`, (event) => seen.push((event as CustomEvent).detail));
            });

            it('a message from another origin, also from the right frame', () => {
                send(frameOf(element), message('height', { height: 900 }), 'https://evil.example');
                send(frameOf(element), message('height', { height: 900 }), 'https://forms.example.org.evil.example');
                send(frameOf(element), message('height', { height: 900 }), 'http://forms.example.org');
                send(frameOf(element), message('height', { height: 900 }), 'null');
                expect(seen).toEqual([]);
                expect(frameOf(element).style.height).toBe('480px');
            });

            it('a message from the right origin but another window', () => {
                send(null, message('height', { height: 900 }));
                window.dispatchEvent(new MessageEvent('message', { data: message('height', { height: 900 }), origin: FORM_ORIGIN, source: window }));
                const stranger = document.createElement('iframe');
                document.body.appendChild(stranger);
                send(stranger, message('height', { height: 900 }));
                expect(seen).toEqual([]);
                expect(frameOf(element).style.height).toBe('480px');
            });

            it.each([
                ['no data', undefined],
                ['a string', 'height'],
                ['another source', { source: 'other', v: 1, type: 'height', height: 900 }],
                ['another version', { source: 'bettercollected-form', v: 2, type: 'height', height: 900 }],
                ['an unknown type', message('answers', { answers: { a: 1 } })],
                ['a height that is no number', message('height', { height: '900' })],
                ['an infinite height', message('height', { height: Infinity })],
                ['a page message (there is none in protocol v1: a page number can reveal an answer)', message('page', { kind: 'question', step: 1, total: 2 })]
            ])('%s', (_name, data) => {
                send(frameOf(element), data);
                expect(seen).toEqual([]);
                expect(frameOf(element).style.height).toBe('480px');
            });
        });

        it('forgets a frame that left the page', () => {
            const element = place();
            load();
            const frame = frameOf(element);
            element.remove();
            window.BetterCollectedEmbed?.scan();
            const handler = vi.fn();
            window.BetterCollectedEmbed?.on('loaded', handler);
            send(frame, message('loaded'));
            expect(handler).not.toHaveBeenCalled();
        });
    });
});
