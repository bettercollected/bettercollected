import { cleanup, render, screen } from '@testing-library/react';
import fs from 'node:fs';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';

import { AppTheme } from '@app/lib/app-theme';
import { AppThemeContext } from '@app/lib/app-theme-context';
import { PIGMENT_MINT, PIGMENT_ORCHID, PIGMENT_SKY, PIGMENT_SUN, PIGMENT_TOMATO } from '@app/views/molecules/theme/pigment-art';

import AppArt from './app-art';
import DaybreakArt from './daybreak-art';
import EmptyState from './empty-state';
import PigmentAppArt from './pigment-app-art';

afterEach(cleanup);

const inScope = (theme: AppTheme | null, node: React.ReactNode) => <AppThemeContext.Provider value={theme}>{node}</AppThemeContext.Provider>;

describe('the creator app picture follows the app theme in scope', () => {
    it("draws Pigment's flat shapes in a Pigment scope, and not the sun and hills", () => {
        const { container } = render(inScope('pigment', <AppArt />));
        expect(screen.getByTestId('pigment-app-art')).toBeInTheDocument();
        expect(container.querySelector('circle.fill-sun')).toBeNull();
        expect(container.querySelector('circle.fill-coral')).toBeNull();
    });

    it('draws exactly what it drew before in Daybreak and with no scope at all (same markup as DaybreakArt)', () => {
        const reference = render(<DaybreakArt />).container.innerHTML;
        cleanup();
        for (const theme of ['daybreak', null] as const) {
            const { container } = render(inScope(theme, <AppArt />));
            expect(container.innerHTML, String(theme)).toBe(reference);
            expect(screen.queryByTestId('pigment-app-art')).toBeNull();
            cleanup();
        }
        const noSpark = render(<DaybreakArt spark={false} />).container.innerHTML;
        cleanup();
        expect(render(<AppArt spark={false} />).container.innerHTML).toBe(noSpark);
    });

    it('takes the theme it is given where the scope is out of reach (the portalled publish dialog)', () => {
        render(<AppArt theme="pigment" />);
        expect(screen.getByTestId('pigment-app-art')).toBeInTheDocument();
        cleanup();
        // an explicit Daybreak wins over a Pigment scope, and an explicit Pigment over no scope
        const { container } = render(inScope('pigment', <AppArt theme="daybreak" />));
        expect(screen.queryByTestId('pigment-app-art')).toBeNull();
        expect(container.querySelector('circle.fill-sun')).not.toBeNull();
    });
});

describe("Pigment's picture", () => {
    const shapes = (container: HTMLElement) => [...container.querySelectorAll('svg > *')] as SVGElement[];

    it.each(['panel', 'band'] as const)('is decorative, still and flat in the %s composition', (variant) => {
        const { container } = render(<PigmentAppArt variant={variant} />);
        const svg = container.querySelector('svg')!;
        expect(svg).toHaveAttribute('aria-hidden', 'true');
        expect(svg).toHaveAttribute('focusable', 'false');
        const html = container.innerHTML;
        // nothing moves, nothing is translucent, nothing blends into brown or grey, nothing speaks
        expect(html).not.toMatch(/animate|transition|keyframes|opacity|gradient|filter|<text|<title|<style|class="[^"]*(animate|opacity|\/\d)/i);
        expect(html).not.toMatch(/\bstyle=/);
        expect(container.querySelector('text')).toBeNull();
    });

    it('uses the five pigments and the iris role, each once or twice, and the same shapes as the ending', () => {
        const { container } = render(<PigmentAppArt variant="panel" />);
        const html = container.innerHTML.toUpperCase();
        for (const pigment of [PIGMENT_TOMATO, PIGMENT_SUN, PIGMENT_MINT, PIGMENT_SKY, PIGMENT_ORCHID]) expect(html).toContain(pigment.toUpperCase());
        // iris comes from the app action role, which is iris in a Pigment scope
        expect(container.querySelectorAll('.fill-app-action')).toHaveLength(1);
        // circle, square, triangle (a three-point path), half-circle (an arc) and ring (a stroked circle)
        expect(container.querySelectorAll('circle').length).toBeGreaterThanOrEqual(3);
        expect(container.querySelectorAll('rect').length).toBeGreaterThanOrEqual(1);
        expect(shapes(container).some((e) => e.tagName === 'path' && /M\d+ \d+H\d+L\d+ \d+Z/.test(e.getAttribute('d') ?? ''))).toBe(true);
        expect(shapes(container).some((e) => e.tagName === 'path' && /a\d+ \d+ 0 0 1/.test(e.getAttribute('d') ?? ''))).toBe(true);
        expect(shapes(container).some((e) => e.tagName === 'circle' && e.getAttribute('fill') === 'none')).toBe(true);
    });

    it("leaves the ring out where a control sits at the corner of the panel (spark off, as for Daybreak's coral spark)", () => {
        const withCorner = render(<AppArt theme="pigment" />).container;
        expect([...withCorner.querySelectorAll('circle')].some((c) => c.getAttribute('fill') === 'none')).toBe(true);
        cleanup();
        const without = render(<AppArt theme="pigment" spark={false} />).container;
        expect([...without.querySelectorAll('circle')].some((c) => c.getAttribute('fill') === 'none')).toBe(false);
        // the other shapes stay: the iris disc, the triangle, the half-circle and the squares
        expect(without.querySelectorAll('.fill-app-action')).toHaveLength(1);
        expect(without.querySelectorAll('path')).toHaveLength(2);
        expect(without.querySelectorAll('rect')).toHaveLength(1);
    });

    it('keeps every shape inside the safe zone: the panel survives the phone crop, the band stays off its edges', () => {
        const box = (e: SVGElement) => {
            const n = (a: string) => Number(e.getAttribute(a));
            if (e.tagName === 'circle') {
                const stroke = e.getAttribute('fill') === 'none' ? n('stroke-width') / 2 : 0;
                return { x0: n('cx') - n('r') - stroke, x1: n('cx') + n('r') + stroke, y0: n('cy') - n('r') - stroke, y1: n('cy') + n('r') + stroke };
            }
            if (e.tagName === 'rect') {
                const rotated = e.hasAttribute('transform');
                const d = rotated ? Math.hypot(n('width'), n('height')) / 2 : 0; // a rotated square: its half-diagonal bounds it
                const cx = n('x') + n('width') / 2;
                const cy = n('y') + n('height') / 2;
                return rotated ? { x0: cx - d, x1: cx + d, y0: cy - d, y1: cy + d } : { x0: n('x'), x1: n('x') + n('width'), y0: n('y'), y1: n('y') + n('height') };
            }
            // a path is M x y, then H x / L x y (the triangle) or an a rx ry 0 0 1 dx 0 arc (the half-circle)
            const d = e.getAttribute('d') ?? '';
            const arc = /^M(\d+) (\d+)a(\d+) \d+ 0 0 1 (\d+) 0Z$/.exec(d);
            if (arc) return { x0: Number(arc[1]), x1: Number(arc[1]) + Number(arc[4]), y0: Number(arc[2]) - Number(arc[3]), y1: Number(arc[2]) };
            const tri = /^M(\d+) (\d+)H(\d+)L(\d+) (\d+)Z$/.exec(d)!;
            const [x1, y1, x2, x3, y3] = tri.slice(1).map(Number);
            return { x0: Math.min(x1, x2, x3), x1: Math.max(x1, x2, x3), y0: Math.min(y1, y3), y1: Math.max(y1, y3) };
        };
        const panel = render(<PigmentAppArt variant="panel" />).container;
        for (const e of shapes(panel)) {
            const b = box(e);
            expect(b.x0, e.outerHTML).toBeGreaterThanOrEqual(130);
            expect(b.x1, e.outerHTML).toBeLessThanOrEqual(557);
            expect(b.y0, e.outerHTML).toBeGreaterThanOrEqual(20);
            expect(b.y1, e.outerHTML).toBeLessThanOrEqual(128);
        }
        cleanup();
        const band = render(<PigmentAppArt variant="band" />).container;
        for (const e of shapes(band)) {
            const b = box(e);
            expect(b.x0, e.outerHTML).toBeGreaterThanOrEqual(8);
            expect(b.x1, e.outerHTML).toBeLessThanOrEqual(272);
            expect(b.y0, e.outerHTML).toBeGreaterThanOrEqual(8);
            expect(b.y1, e.outerHTML).toBeLessThanOrEqual(164);
        }
    });

    it('carries no hex literal of its own: the colours are the ones pigment-art.tsx centralises', () => {
        for (const file of ['pigment-app-art.tsx', 'app-art.tsx']) {
            const source = fs.readFileSync(path.join(__dirname, file), 'utf8');
            expect(source, file).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
        }
    });
});

describe('the empty state', () => {
    it("shows Pigment's shapes on the sunken ground in a Pigment scope", () => {
        const { container } = render(inScope('pigment', <EmptyState title="No forms yet" />));
        expect(screen.getByTestId('pigment-app-art')).toBeInTheDocument();
        const panel = container.querySelector('[data-testid="empty-state"] > div')!;
        expect(panel.className).toContain('bg-sunken');
        expect(panel.className).not.toContain('bg-brand-tint');
    });

    it('is unchanged in Daybreak and with no scope: the sun and hills on the brand tint', () => {
        for (const theme of ['daybreak', null] as const) {
            const { container } = render(inScope(theme, <EmptyState title="No forms yet" />));
            const panel = container.querySelector('[data-testid="empty-state"] > div')!;
            expect(panel.className, String(theme)).toBe('h-[104px] bg-brand-tint sm:h-[148px]');
            expect(panel.innerHTML, String(theme)).toBe(render(<DaybreakArt />).container.innerHTML);
            cleanup();
        }
    });
});
