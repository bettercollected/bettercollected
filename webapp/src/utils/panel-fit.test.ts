import { afterEach, describe, expect, it } from 'vitest';

import { measurePrimaryActionFit, panelFits } from './panel-fit';

describe('panelFits', () => {
    it('opens when the content through the primary action fits above the open panel', () => {
        expect(panelFits({ contentHeight: 400, paddingY: 96, formAreaHeight: 860, panelHeight: 240 })).toBe(true);
        // Exactly fitting counts as fitting.
        expect(panelFits({ contentHeight: 524, paddingY: 96, formAreaHeight: 860, panelHeight: 240 })).toBe(true);
    });

    it('stays closed when the panel would push the primary action out of view', () => {
        expect(panelFits({ contentHeight: 620, paddingY: 48, formAreaHeight: 860, panelHeight: 240 })).toBe(false);
    });
});

describe('measurePrimaryActionFit', () => {
    afterEach(() => {
        document.body.innerHTML = '';
    });

    const rect = (el: Element, top: number, bottom: number) => {
        (el as HTMLElement).getBoundingClientRect = () => ({ top, bottom, left: 0, right: 0, width: 0, height: bottom - top, x: 0, y: top, toJSON: () => ({}) }) as DOMRect;
    };

    const page = ({ contentTop, actionBottom, area }: { contentTop: number; actionBottom: number; area: number }) => {
        document.body.innerHTML = '<div data-fit-area><div style="padding-top:48px;padding-bottom:48px"><div data-primary-content><button data-primary-action>Start</button></div></div></div>';
        rect(document.querySelector('[data-primary-content]')!, contentTop, actionBottom);
        rect(document.querySelector('[data-primary-action]')!, actionBottom - 48, actionBottom);
        Object.defineProperty(document.querySelector('[data-fit-area]')!, 'clientHeight', { value: area });
    };

    it('nothing to protect without a primary action', () => {
        expect(measurePrimaryActionFit(document, { panelHeight: 500, openPanelHeight: 0 })).toBe(true);
    });

    it('measures the content through the action against the area left by the panel', () => {
        page({ contentTop: 0, actionBottom: 500, area: 860 });
        expect(measurePrimaryActionFit(document, { panelHeight: 240, openPanelHeight: 0 })).toBe(true);
        page({ contentTop: 0, actionBottom: 700, area: 860 });
        expect(measurePrimaryActionFit(document, { panelHeight: 240, openPanelHeight: 0 })).toBe(false);
    });

    it('counts the space an already open panel has taken, so it does not close itself', () => {
        // Panel open (240px taken): the area reports 620 but 860 was available.
        page({ contentTop: 0, actionBottom: 500, area: 620 });
        expect(measurePrimaryActionFit(document, { panelHeight: 240, openPanelHeight: 240 })).toBe(true);
    });

    it('takes the organisation logo strip off the room the page has', () => {
        // 524 + 96 fits 860 - 240 exactly; a 96px logo strip above the page does not.
        page({ contentTop: 0, actionBottom: 524, area: 860 });
        expect(measurePrimaryActionFit(document, { panelHeight: 240, openPanelHeight: 0 })).toBe(true);
        const strip = document.createElement('div');
        strip.setAttribute('data-fit-reserve', '');
        rect(strip, 0, 96);
        document.querySelector('[data-fit-area]')!.prepend(strip);
        expect(measurePrimaryActionFit(document, { panelHeight: 240, openPanelHeight: 0 })).toBe(false);
    });
});
