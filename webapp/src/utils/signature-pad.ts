/**
 * The drawing of a signature, without the page: strokes in a fixed
 * coordinate space (PAD_WIDTH x PAD_HEIGHT), how pointer positions become
 * points, how they are painted, and whether anything is drawn.
 *
 * The canvas keeps a fixed resolution of PAD_WIDTH x PAD_HEIGHT times
 * PAD_SCALE (1200 x 480 pixels, at most what the server takes: backend
 * services/signatures.py) and is shown at any width, so the PNG it makes is
 * the same on every screen. Ink is dark on transparent pixels: the box shows
 * its own light background.
 */

export interface Point {
    x: number;
    y: number;
}
export type Stroke = Point[];

export const PAD_WIDTH = 600;
export const PAD_HEIGHT = 240;
/** Pixels per unit of the pad's space: the exported image is PAD_WIDTH * PAD_SCALE wide. */
export const PAD_SCALE = 2;
export const INK = '#111827';
export const INK_WIDTH = 3;
/** Points closer than this (in pad units) to the last one add nothing. */
const MIN_STEP = 0.75;
/** A stroke may hold this many points; a longer scribble stops adding. */
export const MAX_POINTS = 6000;

const clamp = (value: number, low: number, high: number) => Math.min(Math.max(value, low), high);

/** A pointer position (client coordinates) in the pad's space, kept inside it. */
export function pointFrom(rect: { left: number; top: number; width: number; height: number }, clientX: number, clientY: number): Point {
    const width = rect.width || 1;
    const height = rect.height || 1;
    return { x: clamp(((clientX - rect.left) / width) * PAD_WIDTH, 0, PAD_WIDTH), y: clamp(((clientY - rect.top) / height) * PAD_HEIGHT, 0, PAD_HEIGHT) };
}

/** A new set of strokes with one more, started at `point`. */
export const beginStroke = (strokes: ReadonlyArray<Stroke>, point: Point): Stroke[] => [...strokes, [point]];

/** The strokes with `point` added to the last one (nothing when it is no step from the last point, or there is no stroke). */
export function extendStroke(strokes: ReadonlyArray<Stroke>, point: Point): Stroke[] {
    if (!strokes.length) return [...strokes];
    const last = strokes[strokes.length - 1];
    const tip = last[last.length - 1];
    if (last.length >= MAX_POINTS || (tip && Math.hypot(point.x - tip.x, point.y - tip.y) < MIN_STEP)) return [...strokes];
    return [...strokes.slice(0, -1), [...last, point]];
}

/** Is anything drawn? A single tap is a dot. */
export const hasInk = (strokes: ReadonlyArray<Stroke>): boolean => strokes.some((stroke) => stroke.length > 0);

/** The minimal drawing context the painting needs (a CanvasRenderingContext2D has it). */
export interface PadContext {
    clearRect(x: number, y: number, w: number, h: number): void;
    beginPath(): void;
    moveTo(x: number, y: number): void;
    quadraticCurveTo(cx: number, cy: number, x: number, y: number): void;
    lineTo(x: number, y: number): void;
    stroke(): void;
    arc(x: number, y: number, radius: number, start: number, end: number): void;
    fill(): void;
    setTransform(a: number, b: number, c: number, d: number, e: number, f: number): void;
    lineWidth: number;
    lineCap: CanvasLineCap;
    lineJoin: CanvasLineJoin;
    strokeStyle: string | CanvasGradient | CanvasPattern;
    fillStyle: string | CanvasGradient | CanvasPattern;
}

/** Paint the strokes, smoothed through the middle of each pair of points, as dark ink on transparent pixels. */
export function paintStrokes(context: PadContext, strokes: ReadonlyArray<Stroke>, scale: number = PAD_SCALE): void {
    context.setTransform(scale, 0, 0, scale, 0, 0);
    context.clearRect(0, 0, PAD_WIDTH, PAD_HEIGHT);
    context.strokeStyle = INK;
    context.fillStyle = INK;
    context.lineWidth = INK_WIDTH;
    context.lineCap = 'round';
    context.lineJoin = 'round';
    for (const stroke of strokes) {
        if (!stroke.length) continue;
        if (stroke.length < 3) {
            // a tap, or two points: a dot or a straight line
            const [first, second] = stroke;
            if (!second || (first.x === second.x && first.y === second.y)) {
                context.beginPath();
                context.arc(first.x, first.y, INK_WIDTH / 2, 0, Math.PI * 2);
                context.fill();
            } else {
                context.beginPath();
                context.moveTo(first.x, first.y);
                context.lineTo(second.x, second.y);
                context.stroke();
            }
            continue;
        }
        context.beginPath();
        context.moveTo(stroke[0].x, stroke[0].y);
        for (let i = 1; i < stroke.length - 1; i++) {
            const mid = { x: (stroke[i].x + stroke[i + 1].x) / 2, y: (stroke[i].y + stroke[i + 1].y) / 2 };
            context.quadraticCurveTo(stroke[i].x, stroke[i].y, mid.x, mid.y);
        }
        const end = stroke[stroke.length - 1];
        context.lineTo(end.x, end.y);
        context.stroke();
    }
}

/** The PNG of a canvas (transparent where nothing is drawn), or null when the browser cannot make one. */
export function canvasToPng(canvas: Pick<HTMLCanvasElement, 'toBlob'>): Promise<Blob | null> {
    return new Promise((resolve) => {
        try {
            canvas.toBlob((blob) => resolve(blob), 'image/png');
        } catch {
            resolve(null);
        }
    });
}

/** The name the drawn image is sent under (its id is what the answer holds). */
export const SIGNATURE_FILE_NAME = 'signature.png';
