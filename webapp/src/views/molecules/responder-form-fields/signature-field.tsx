import { useEffect, useId, useMemo, useRef, useState } from 'react';

import { v4 } from 'uuid';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { cn } from '@app/shadcn/util/lib';
import { useFormState } from '@app/store/jotai/form';
import useFormAtom from '@app/store/jotai/form-file';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { SIGNATURE_NAME_MAX, TYPED_SIGNATURE_FONT, answerSignature, normalisedName } from '@app/utils/signature';
import { PAD_HEIGHT, PAD_SCALE, PAD_WIDTH, SIGNATURE_FILE_NAME, SIGNATURE_MAX_BYTES, Stroke, beginStroke, canvasToPng, extendStroke, hasInk, paintStrokes, pointFrom } from '@app/utils/signature-pad';
import { ChoiceContent, choiceRowStyle } from '@app/views/atoms/choice';
import { invalidEdge } from '@app/views/molecules/theme/theme-shared';

import { useEnterToNextQuestion } from './next-question';
import { joinIds, useQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

interface ISignatureField {
    field: StandardFormFieldDto;
    slide?: StandardFormFieldDto;
    isBuilder?: boolean;
}

type Method = 'drawn' | 'typed';

/** A pen's eraser end presses button 5 (Pointer Events): it never draws. */
const ERASER_BUTTON = 5;

/** `value` cut to `max` characters as the server counts them (code points, not UTF-16 units). */
const cutToCharacters = (value: string, max: number) => {
    const characters = Array.from(value);
    return characters.length > max ? characters.slice(0, max).join('') : value;
};

/**
 * A signature question. Two ways to sign, both complete: draw in a box with a
 * mouse, finger or pen, or type your name. The method is chosen first (two
 * radio buttons, before the box in the tab order), so a person who cannot
 * draw, or uses a keyboard or screen reader, reaches the typed way at once.
 *
 * Drawing makes a PNG (the same size on every screen); it goes along with the
 * submission as a file part and the answer holds only its id. Typing stores
 * the name. Either way the server stamps the time and re-checks everything.
 * This records a drawn or typed name: it does not check who signed.
 */
function SignatureFieldSection({ field, isBuilder }: ISignatureField) {
    const { theme } = useFormState();
    const { formResponse, setFormResponse, addFieldSignatureAnswer, removeAnswer } = useFormResponse();
    const { files, addFile, removeFile } = useFormAtom();
    const { t } = useRespondentLanguage();
    const onKeyDown = useEnterToNextQuestion(field);
    const uid = useId();
    const hintId = `${uid}-hint`;
    const statusId = `${uid}-status`;
    const errorId = `${uid}-name-error`;
    const nameId = `signature-name-${field.id}`;
    const { label: question, control, group } = useQuestionLabel(hintId, statusId);

    const stored = answerSignature(formResponse.answers?.[field.id]);
    const [method, setMethod] = useState<Method>(stored?.method === 'typed' ? 'typed' : 'drawn');
    // The way of signing as the latest event set it, for work that finishes after an await.
    const methodRef = useRef<Method>(method);
    const [draft, setDraft] = useState(stored?.method === 'typed' ? (stored.name ?? '') : '');
    const [status, setStatus] = useState('');
    const [padUnavailable, setPadUnavailable] = useState(false);
    // The drawing made a PNG over the size the server takes (too many strokes): said next to the box until the next stroke.
    const [tooDetailed, setTooDetailed] = useState(false);
    // "Signature added" is said once per drawing: not again for each further stroke, until it is cleared or the way of signing changes.
    const announced = useRef(false);
    // What is drawn (kept while the person looks at the other way of signing) and the box it is drawn in.
    const strokes = useRef<Stroke[]>([]);
    const [inked, setInked] = useState(false);
    // The one pointer that draws (a second finger, a palm or another pen is ignored until it is lifted).
    const activePointer = useRef<number | null>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    // Each commit, Clear and change of method takes the next number; a PNG made for an older one is dropped.
    const commitSeq = useRef(0);
    // The drawing this browser holds, set aside while a name is typed and given back on returning to drawing.
    const setAside = useRef<{ fileId: string; fileName: string; file: File } | null>(null);
    // A new stroke started on top of a held drawing: too little ink brings the held one back instead of removing it.
    const overHeld = useRef(false);

    // The drawing this browser holds for the question (shown again when the question is revisited).
    const held = files.find((item) => item.fieldId === field.id)?.file;
    const heldUrl = useMemo(() => (held && typeof URL !== 'undefined' && URL.createObjectURL ? URL.createObjectURL(held) : undefined), [held]);
    useEffect(() => {
        return () => {
            if (heldUrl && URL.revokeObjectURL) URL.revokeObjectURL(heldUrl);
        };
    }, [heldUrl]);
    const showHeld = method === 'drawn' && stored?.method === 'drawn' && !!heldUrl && !inked;
    // A drawn signature the response already has but this browser does not hold (editing a submitted response): it stays until a new one is drawn.
    const onFile = method === 'drawn' && stored?.method === 'drawn' && !held && !inked;

    /** The question's "please answer" mark goes as soon as the person starts to answer (it is only re-set by the next Continue). */
    const clearFlag = () => {
        if (!formResponse.invalidFields?.[field.id]) return;
        setFormResponse((previous) => {
            const { [field.id]: _gone, ...rest } = previous.invalidFields ?? {};
            return { ...previous, invalidFields: rest };
        });
    };

    const repaint = () => {
        const context = canvasRef.current?.getContext('2d');
        if (!context) {
            setPadUnavailable(true);
            return;
        }
        paintStrokes(context, strokes.current);
    };

    useEffect(() => {
        if (method === 'drawn') repaint();
    }, [method, showHeld]);

    /** The drawing as it is now: a file part and the answer, or no answer when too little is drawn to count. */
    const commitDrawing = async () => {
        const seq = ++commitSeq.current;
        if (!hasInk(strokes.current)) {
            if (overHeld.current) {
                // a tap on the drawing already held: it stays, as it was
                overHeld.current = false;
                strokes.current = [];
                setInked(false);
                repaint();
                return;
            }
            removeFile(field.id);
            removeAnswer(field.id);
            return;
        }
        const canvas = canvasRef.current;
        const blob = canvas ? await canvasToPng(canvas) : null;
        // Cleared, drawn again or switched to typing while the PNG was made: this one is out of date.
        if (seq !== commitSeq.current || methodRef.current !== 'drawn') return;
        if (!blob) {
            setPadUnavailable(true);
            return;
        }
        if (blob.size > SIGNATURE_MAX_BYTES) {
            // too detailed for the server: nothing is sent; the box is emptied so the next drawing starts clean
            overHeld.current = false;
            strokes.current = [];
            announced.current = false;
            setInked(false);
            removeFile(field.id);
            removeAnswer(field.id);
            setTooDetailed(true);
            setStatus('');
            repaint();
            return;
        }
        overHeld.current = false;
        setAside.current = null;
        const fileId = v4();
        addFile(field.id, fileId, SIGNATURE_FILE_NAME, new File([blob], SIGNATURE_FILE_NAME, { type: 'image/png' }));
        addFieldSignatureAnswer(field.id, { method: 'drawn', file_id: fileId });
        if (!announced.current) {
            announced.current = true;
            setStatus(t('SIGNATURE.ADDED'));
        }
    };

    const pointerOf = (event: React.PointerEvent<HTMLCanvasElement>) => event.pointerId ?? -1;
    const down = (event: React.PointerEvent<HTMLCanvasElement>) => {
        if (isBuilder || activePointer.current !== null) return;
        if ((event.pointerType === 'mouse' && event.button !== 0) || event.button === ERASER_BUTTON) return;
        const rect = event.currentTarget.getBoundingClientRect();
        activePointer.current = pointerOf(event);
        if (showHeld) overHeld.current = true;
        setTooDetailed(false);
        clearFlag();
        try {
            event.currentTarget.setPointerCapture(event.pointerId);
        } catch {
            // a pointer that is already gone: the strokes still work
        }
        strokes.current = beginStroke(strokes.current, pointFrom(rect, event.clientX, event.clientY));
        setInked(true);
        repaint();
    };
    const move = (event: React.PointerEvent<HTMLCanvasElement>) => {
        if (activePointer.current === null || pointerOf(event) !== activePointer.current) return;
        const rect = event.currentTarget.getBoundingClientRect();
        strokes.current = extendStroke(strokes.current, pointFrom(rect, event.clientX, event.clientY));
        repaint();
    };
    const up = (event: React.PointerEvent<HTMLCanvasElement>) => {
        if (activePointer.current === null || pointerOf(event) !== activePointer.current) return;
        activePointer.current = null;
        void commitDrawing();
    };

    const clear = () => {
        commitSeq.current++;
        setAside.current = null;
        overHeld.current = false;
        strokes.current = [];
        announced.current = false;
        setTooDetailed(false);
        setInked(false);
        removeFile(field.id);
        removeAnswer(field.id);
        setStatus(t('SIGNATURE.CLEARED'));
        repaint();
    };

    const choose = (next: Method) => {
        if (isBuilder || next === method) return;
        commitSeq.current++;
        methodRef.current = next;
        activePointer.current = null;
        announced.current = false;
        setTooDetailed(false);
        setMethod(next);
        setStatus('');
        if (next === 'typed') {
            // the drawing is set aside (kept on the page, not sent) while a name is typed
            const heldEntry = files.find((item) => item.fieldId === field.id);
            if (heldEntry) setAside.current = { fileId: heldEntry.fileId, fileName: heldEntry.fileName, file: heldEntry.file };
            removeFile(field.id);
            const name = normalisedName(draft);
            if (name) addFieldSignatureAnswer(field.id, { method: 'typed', name });
            else removeAnswer(field.id);
        } else if (setAside.current) {
            // the drawing set aside goes again as it was (same image, same id)
            const aside = setAside.current;
            setAside.current = null;
            addFile(field.id, aside.fileId, aside.fileName, aside.file);
            addFieldSignatureAnswer(field.id, { method: 'drawn', file_id: aside.fileId });
        } else {
            removeAnswer(field.id);
            if (hasInk(strokes.current)) window.setTimeout(() => void commitDrawing(), 0);
        }
    };

    const typedName = normalisedName(draft);
    const badName = draft.trim() !== '' && typedName === undefined;
    // After Continue the question's own message says what is wrong (QuestionWrapper); until then this one does.
    const wrapperError = !!question?.invalid;
    const ownError = badName && !wrapperError;
    const type = (typed: string) => {
        const value = cutToCharacters(typed, SIGNATURE_NAME_MAX);
        setDraft(value);
        clearFlag();
        const name = normalisedName(value);
        if (name) {
            addFieldSignatureAnswer(field.id, { method: 'typed', name });
            setStatus('');
        } else if (value.trim()) {
            // a name with characters that cannot be used is kept as typed, so the page flags it and never sends it (as an impossible day is)
            addFieldSignatureAnswer(field.id, { method: 'typed', name: value.trim() });
        } else removeAnswer(field.id);
    };

    const border = theme?.tertiary ?? '#818CA0';
    const padEdge = wrapperError ? invalidEdge(theme) : '#667085';
    const radios: Array<{ value: Method; label: string }> = [
        { value: 'drawn', label: t('SIGNATURE.DRAW') },
        { value: 'typed', label: t('SIGNATURE.TYPE') }
    ];

    return (
        <div className="flex flex-col gap-3">
            <div role="radiogroup" aria-labelledby={question?.labelledBy} aria-label={question?.labelledBy ? undefined : t('SIGNATURE.METHOD')} aria-describedby={group['aria-describedby']} className="flex flex-wrap gap-2">
                {radios.map((radio) => {
                    // the option rows of a choice question (DESIGN.md, choice rows): a ring or dot, and the chosen one in semibold
                    const chosen = method === radio.value;
                    const row = choiceRowStyle(theme, chosen);
                    return (
                        <label key={radio.value} className={cn(row.className, 'w-auto min-w-40 flex-1 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2')} style={row.style} data-chosen={chosen || undefined}>
                            <input type="radio" name={`signature-method-${field.id}`} value={radio.value} checked={chosen} disabled={isBuilder} onChange={() => choose(radio.value)} className="sr-only" />
                            <ChoiceContent kind="radio" selected={chosen} theme={theme} solid={row.solid}>
                                {radio.label}
                            </ChoiceContent>
                        </label>
                    );
                })}
            </div>

            {method === 'drawn' ? (
                <div className="flex flex-col gap-2">
                    <div className="relative w-full overflow-hidden rounded border-2 bg-white" data-signature-pad style={{ borderColor: padEdge, aspectRatio: `${PAD_WIDTH} / ${PAD_HEIGHT}`, borderRadius: 6 }}>
                        {showHeld && (
                            // a local preview of the drawing this browser holds (a blob address): next/image has nothing to optimise;
                            // under the canvas, so drawing on it starts a new signature (a tap alone keeps this one)
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={heldUrl} alt={t('SIGNATURE.DRAWN_ALT')} className="pointer-events-none absolute inset-0 h-full w-full object-contain" />
                        )}
                        <canvas
                            ref={canvasRef}
                            role="img"
                            aria-label={t('SIGNATURE.PAD_LABEL')}
                            aria-describedby={hintId}
                            width={PAD_WIDTH * PAD_SCALE}
                            height={PAD_HEIGHT * PAD_SCALE}
                            className="absolute inset-0 h-full w-full"
                            style={{ touchAction: 'none', cursor: isBuilder ? 'default' : 'crosshair', userSelect: 'none' }}
                            onPointerDown={down}
                            onPointerMove={move}
                            onPointerUp={up}
                            onPointerCancel={up}
                            onLostPointerCapture={up}
                        />
                        {!inked && !showHeld && (
                            <span aria-hidden="true" className="pointer-events-none absolute inset-0 flex items-end p-3 text-sm" style={{ color: '#667085' }}>
                                <span className="w-full border-b border-dashed pb-1" style={{ borderColor: '#98A2B3' }}>
                                    {t('SIGNATURE.SIGN_HERE')}
                                </span>
                            </span>
                        )}
                    </div>
                    {onFile && (
                        <p data-signature-on-file className="m-0 text-sm font-medium" style={{ color: theme?.primary }}>
                            {t('SIGNATURE.ON_FILE')}
                        </p>
                    )}
                    {tooDetailed && (
                        <p role="alert" data-signature-too-detailed className="m-0 text-[15px] leading-snug font-medium" style={{ color: theme?.primary }}>
                            {t('SIGNATURE.TOO_DETAILED')}
                        </p>
                    )}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                        <p id={hintId} className="m-0 text-sm text-[#667085]">
                            {padUnavailable ? t('SIGNATURE.PAD_UNAVAILABLE') : t('SIGNATURE.PAD_HINT')}
                        </p>
                        <button
                            type="button"
                            onClick={clear}
                            disabled={isBuilder || (!inked && !showHeld)}
                            aria-label={t('SIGNATURE.CLEAR_LABEL')}
                            className="min-h-11 min-w-11 cursor-pointer rounded border px-4 py-2 text-base font-medium disabled:cursor-not-allowed disabled:opacity-50"
                            style={{ borderColor: border, color: theme?.primary }}
                        >
                            {t('SIGNATURE.CLEAR')}
                        </button>
                    </div>
                </div>
            ) : (
                <div className="flex flex-col gap-2">
                    <label htmlFor={nameId} className="text-sm font-medium" style={{ color: theme?.primary }}>
                        {t('SIGNATURE.NAME_LABEL')}
                    </label>
                    <FieldInput
                        {...control}
                        id={nameId}
                        type="text"
                        autoComplete="name"
                        // a hard bound in UTF-16 units; the 100 characters are counted as the server counts them (type above)
                        maxLength={SIGNATURE_NAME_MAX * 2}
                        value={draft}
                        disabled={isBuilder}
                        aria-labelledby={undefined}
                        aria-describedby={joinIds(control['aria-describedby'], ownError && errorId)}
                        aria-invalid={badName || wrapperError || undefined}
                        // QuestionWrapper leaves this mark of the field's own alone while the question has no error of its own
                        data-local-invalid={badName || undefined}
                        $formTheme={theme}
                        onChange={(event: React.ChangeEvent<HTMLInputElement>) => type(event.target.value)}
                        onKeyDown={onKeyDown}
                        className="min-h-12"
                    />
                    {typedName && (
                        // What the typed name will look like where it is shown: the text is the signature, the style only a flourish.
                        <p aria-hidden="true" className="m-0 overflow-hidden border-b px-1 pt-2 pb-1 text-3xl [overflow-wrap:anywhere] italic" style={{ fontFamily: TYPED_SIGNATURE_FONT, borderColor: border, color: theme?.primary ?? '#111827' }}>
                            {typedName}
                        </p>
                    )}
                    <p id={hintId} className="m-0 text-sm text-[#667085]">
                        {t('SIGNATURE.NAME_HINT')}
                    </p>
                    {/* Said politely as it appears; gone once the question's own message (after Continue) says it, so it is never heard twice. */}
                    <p id={errorId} aria-live="polite" className={cn('m-0 text-[15px] leading-snug font-medium', !ownError && 'sr-only')} style={{ color: theme?.primary }}>
                        {ownError ? t('RULE.FORMAT_SIGNATURE') : ''}
                    </p>
                </div>
            )}
            {/* Added and cleared are announced politely; the question's own message says what is wrong. */}
            <p id={statusId} role="status" className="sr-only">
                {status}
            </p>
        </div>
    );
}

const SignatureField = ({ field, slide, isBuilder = false }: ISignatureField) =>
    isBuilder ? (
        <SignatureFieldSection field={field} slide={slide} isBuilder />
    ) : (
        <QuestionWrapper field={field}>
            <SignatureFieldSection field={field} slide={slide} />
        </QuestionWrapper>
    );

export default SignatureField;
