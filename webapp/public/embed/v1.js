/*!
 * BetterCollected form embed, protocol v1 (docs/embed.md).
 *
 * <div data-bc-form="https://forms.example.org/acme/forms/contact"></div>
 * <script async src="https://forms.example.org/embed/v1.js" integrity="sha384-..." crossorigin="anonymous"></script>
 *
 * This file never changes once released: its address and its sha384 are in the snippet the share dialog
 * shows (src/lib/embed/embed-script.ts, with a test that pins the hash). A change is a new file (v2.js).
 * /embed.js is a moving alias of the current version, for pages that do not pin it.
 *
 * Shows each [data-bc-form] placeholder's form in an iframe and keeps the frame as tall as the form's
 * page needs. The form tells this page only that it loaded, how tall it needs to be and that it was
 * submitted (no page number, never an answer; only while the server has embedding on). A message counts only when it comes from
 * the frame this script made and from the origin of the form's address. Nothing is ever sent to the form
 * but the address's own query (embed=1, the host's origin, an optional language).
 *
 * Attributes: data-bc-form (https address of the form; http only for localhost), data-bc-title (the
 * frame's accessible name, default "Form"), data-bc-min-height (px, 240-4000, default 480),
 * data-bc-lang (en|nl), data-bc-theme (light|dark|auto: the frame's colour scheme only).
 * API: BetterCollectedEmbed.scan(root), .on(type, fn), .version. DOM events on the placeholder:
 * bc-form:loaded, bc-form:height, bc-form:submitted (detail = the message's data).
 */
(function () {
    'use strict';

    var VERSION = 1;
    var SOURCE = 'bettercollected-form';
    var MIN_HEIGHT = 240;
    var MAX_HEIGHT = 4000;
    var DEFAULT_HEIGHT = 480;

    var existing = window.BetterCollectedEmbed;
    if (existing && typeof existing.scan === 'function') {
        existing.scan();
        return;
    }

    var instances = [];
    var listeners = {};

    function clamp(value, low, high) {
        return Math.min(high, Math.max(low, value));
    }

    /** localhost, 127.0.0.1 and the names under .localhost (loopback by definition): where http is fine. */
    function isLocal(hostname) {
        return hostname === 'localhost' || hostname === '127.0.0.1' || /\.localhost$/.test(hostname);
    }

    /** The form's address as a URL, or null: https only (http for localhost), no credentials, no fragment. */
    function parseFormUrl(value) {
        var url;
        try {
            url = new URL(String(value || '').trim());
        } catch (error) {
            return null;
        }
        var secure = url.protocol === 'https:';
        var local = url.protocol === 'http:' && isLocal(url.hostname);
        if (!secure && !local) return null;
        if (url.username || url.password || url.hash) return null;
        return url;
    }

    function reducedMotion() {
        return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    }

    function dispatch(instance, type, detail) {
        var name = 'bc-form:' + type;
        try {
            instance.element.dispatchEvent(new CustomEvent(name, { bubbles: true, detail: detail }));
        } catch (error) {
            /* a host handler's error is the host's */
        }
        (listeners[type] || []).slice().forEach(function (handler) {
            try {
                handler(detail, instance.element);
            } catch (error) {
                /* same */
            }
        });
    }

    /** The message's payload, reduced to the known shape of its type, or null. Unknown keys are dropped. */
    function payloadOf(data) {
        if (!data || typeof data !== 'object' || data.source !== SOURCE || data.v !== VERSION) return null;
        switch (data.type) {
            case 'loaded':
            case 'submitted':
                return { type: data.type };
            case 'height':
                if (typeof data.height !== 'number' || !isFinite(data.height)) return null;
                return { type: 'height', height: Math.round(clamp(data.height, MIN_HEIGHT, MAX_HEIGHT)) };
            default:
                return null;
        }
    }

    function onMessage(event) {
        var instance = null;
        for (var i = 0; i < instances.length; i++) {
            if (instances[i].frame.contentWindow && instances[i].frame.contentWindow === event.source) {
                instance = instances[i];
                break;
            }
        }
        // only the frame this script made, and only from the form's own origin
        if (!instance || event.origin !== instance.origin) return;
        var payload = payloadOf(event.data);
        if (!payload) return;
        if (payload.type === 'height') {
            instance.frame.style.height = payload.height + 'px';
        } else if (payload.type === 'loaded') {
            instance.element.setAttribute('data-bc-loaded', '');
        }
        dispatch(instance, payload.type, payload);
    }

    function minHeightOf(element) {
        var value = parseInt(element.getAttribute('data-bc-min-height'), 10);
        return isFinite(value) ? clamp(value, MIN_HEIGHT, MAX_HEIGHT) : DEFAULT_HEIGHT;
    }

    function mount(element) {
        if (element.hasAttribute('data-bc-ready')) return;
        var url = parseFormUrl(element.getAttribute('data-bc-form'));
        element.setAttribute('data-bc-ready', '');
        if (!url) {
            element.setAttribute('data-bc-error', 'address');
            return;
        }
        var origin = url.origin;
        var src = new URL(url.href);
        src.searchParams.set('embed', '1');
        // the one origin the form may answer to; a page without one (file:, a sandbox) gets no messages
        if (window.location.origin && window.location.origin !== 'null') {
            src.searchParams.set('parent', window.location.origin);
        }
        var lang = element.getAttribute('data-bc-lang');
        if (lang === 'en' || lang === 'nl') src.searchParams.set('lang', lang);

        var frame = document.createElement('iframe');
        frame.setAttribute('src', src.href);
        frame.setAttribute('title', element.getAttribute('data-bc-title') || 'Form');
        frame.setAttribute('loading', 'lazy');
        frame.setAttribute('referrerpolicy', 'origin');
        frame.setAttribute('allow', '');
        var scheme = element.getAttribute('data-bc-theme');
        var style = frame.style;
        style.display = 'block';
        style.width = '100%';
        style.border = '0';
        style.height = minHeightOf(element) + 'px';
        if (scheme === 'light' || scheme === 'dark') style.colorScheme = scheme;
        if (!reducedMotion()) style.transition = 'height 150ms ease';
        element.appendChild(frame);
        instances.push({ element: element, frame: frame, origin: origin });
    }

    function scan(root) {
        instances = instances.filter(function (instance) {
            return document.documentElement.contains(instance.frame);
        });
        var scope = root && root.querySelectorAll ? root : document;
        var found = scope.querySelectorAll('[data-bc-form]');
        for (var i = 0; i < found.length; i++) mount(found[i]);
    }

    function on(type, handler) {
        if (typeof handler !== 'function') return function () {};
        (listeners[type] = listeners[type] || []).push(handler);
        return function () {
            listeners[type] = (listeners[type] || []).filter(function (item) {
                return item !== handler;
            });
        };
    }

    window.addEventListener('message', onMessage);
    window.BetterCollectedEmbed = { version: VERSION, scan: scan, on: on };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            scan();
        });
    } else {
        scan();
    }
})();
