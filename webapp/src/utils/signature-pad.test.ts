import { describe, expect, it, vi } from 'vitest';

import { MAX_POINTS, PAD_HEIGHT, PAD_SCALE, PAD_WIDTH, beginStroke, canvasToPng, extendStroke, hasInk, paintStrokes, pointFrom } from './signature-pad';

const rect = { left: 10, top: 20, width: 300, height: 100 };

describe('pointFrom', () => {
    it('maps a pointer position into the pad space, whatever the box is shown at', () => {
        expect(pointFrom(rect, 10, 20)).toEqual({ x: 0, y: 0 });
        expect(pointFrom(rect, 160, 70)).toEqual({ x: PAD_WIDTH / 2, y: PAD_HEIGHT / 2 });
        expect(pointFrom(rect, 310, 120)).toEqual({ x: PAD_WIDTH, y: PAD_HEIGHT });
    });

    it('keeps a point that left the box inside it, and survives a box with no size', () => {
        expect(pointFrom(rect, -500, 9999)).toEqual({ x: 0, y: PAD_HEIGHT });
        expect(Number.isFinite(pointFrom({ left: 0, top: 0, width: 0, height: 0 }, 5, 5).x)).toBe(true);
    });
});

describe('strokes', () => {
    it('start with a tap and grow with moves', () => {
        let strokes = beginStroke([], { x: 10, y: 10 });
        expect(hasInk(strokes)).toBe(true);
        strokes = extendStroke(strokes, { x: 20, y: 20 });
        expect(strokes).toEqual([
            [
                { x: 10, y: 10 },
                { x: 20, y: 20 }
            ]
        ]);
        strokes = beginStroke(strokes, { x: 50, y: 50 });
        expect(strokes).toHaveLength(2);
    });

    it('never change the strokes they were given', () => {
        const first = beginStroke([], { x: 1, y: 1 });
        const second = extendStroke(first, { x: 30, y: 30 });
        expect(first[0]).toHaveLength(1);
        expect(second[0]).toHaveLength(2);
    });

    it('ignore a move that is no step, a move with no stroke, and a scribble past the cap', () => {
        const strokes = beginStroke([], { x: 10, y: 10 });
        expect(extendStroke(strokes, { x: 10.2, y: 10.2 })[0]).toHaveLength(1);
        expect(extendStroke([], { x: 5, y: 5 })).toEqual([]);
        let long = strokes;
        for (let i = 0; i < MAX_POINTS + 50; i++) long = extendStroke(long, { x: (i % 500) + 20, y: (i % 150) + 20 + (i % 2) * 10 });
        expect(long[0].length).toBeLessThanOrEqual(MAX_POINTS);
    });

    it('have no ink when none are drawn', () => {
        expect(hasInk([])).toBe(false);
        expect(hasInk([[]])).toBe(false);
    });
});

function fakeContext() {
    const calls: string[] = [];
    const record =
        (name: string) =>
        (..._args: unknown[]) =>
            void calls.push(name);
    return {
        calls,
        context: {
            clearRect: record('clearRect'),
            beginPath: record('beginPath'),
            moveTo: record('moveTo'),
            quadraticCurveTo: record('quadraticCurveTo'),
            lineTo: record('lineTo'),
            stroke: record('stroke'),
            arc: record('arc'),
            fill: record('fill'),
            setTransform: vi.fn(),
            lineWidth: 0,
            lineCap: 'butt' as CanvasLineCap,
            lineJoin: 'miter' as CanvasLineJoin,
            strokeStyle: '',
            fillStyle: ''
        }
    };
}

describe('paintStrokes', () => {
    it('clears the pad and draws a tap as a dot, two points as a line, more as a smooth curve', () => {
        const { calls, context } = fakeContext();
        paintStrokes(context, [
            [{ x: 5, y: 5 }],
            [
                { x: 10, y: 10 },
                { x: 40, y: 40 }
            ],
            [
                { x: 50, y: 50 },
                { x: 60, y: 70 },
                { x: 80, y: 60 },
                { x: 90, y: 90 }
            ]
        ]);
        expect(context.setTransform).toHaveBeenCalledWith(PAD_SCALE, 0, 0, PAD_SCALE, 0, 0);
        expect(calls[0]).toBe('clearRect');
        expect(calls).toContain('arc');
        expect(calls).toContain('lineTo');
        expect(calls).toContain('quadraticCurveTo');
        expect(context.lineCap).toBe('round');
        // dark ink; the box shows its own light background
        expect(context.strokeStyle).toMatch(/^#1/);
    });

    it('draws nothing but the clear for no strokes, and a single repeated point as a dot', () => {
        const none = fakeContext();
        paintStrokes(none.context, []);
        expect(none.calls).toEqual(['clearRect']);
        const same = fakeContext();
        paintStrokes(same.context, [
            [
                { x: 5, y: 5 },
                { x: 5, y: 5 }
            ]
        ]);
        expect(same.calls).toContain('arc');
    });
});

describe('canvasToPng', () => {
    it('gives the canvas PNG, or null when the browser cannot make one', async () => {
        const blob = new Blob(['x'], { type: 'image/png' });
        await expect(canvasToPng({ toBlob: (cb: BlobCallback, type?: string) => (expect(type).toBe('image/png'), cb(blob)) })).resolves.toBe(blob);
        await expect(canvasToPng({ toBlob: (cb: BlobCallback) => cb(null) })).resolves.toBeNull();
        await expect(
            canvasToPng({
                toBlob: () => {
                    throw new Error('tainted');
                }
            })
        ).resolves.toBeNull();
    });
});
