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
import { PAD_HEIGHT, PAD_SCALE, PAD_WIDTH, SIGNATURE_FILE_NAME, Stroke, beginStroke, canvasToPng, extendStroke, hasInk, paintStrokes, pointFrom } from '@app/utils/signature-pad';

import { useEnterToNextQuestion } from './next-question';
import { joinIds, useQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

interface ISignatureField {
    field: StandardFormFieldDto;
    slide?: StandardFormFieldDto;
    isBuilder?: boolean;
}

type Method = 'drawn' | 'typed';

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
    const { formResponse, addFieldSignatureAnswer, removeAnswer } = useFormResponse();
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
    const [draft, setDraft] = useState(stored?.method === 'typed' ? (stored.name ?? '') : '');
    const [status, setStatus] = useState('');
    const [padUnavailable, setPadUnavailable] = useState(false);
    // What is drawn (kept while the person looks at the other way of signing) and the box it is drawn in.
    const strokes = useRef<Stroke[]>([]);
    const [inked, setInked] = useState(false);
    const drawing = useRef(false);
    const canvasRef = useRef<HTMLCanvasElement>(null);

    // The drawing this browser holds for the question (shown again when the question is revisited).
    const held = files.find((item) => item.fieldId === field.id)?.file;
    const heldUrl = useMemo(() => (held && typeof URL !== 'undefined' && URL.createObjectURL ? URL.createObjectURL(held) : undefined), [held]);
    useEffect(() => {
        return () => {
            if (heldUrl && URL.revokeObjectURL) URL.revokeObjectURL(heldUrl);
        };
    }, [heldUrl]);
    const showHeld = method === 'drawn' && stored?.method === 'drawn' && !!heldUrl && !inked;

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

    /** The drawing as it is now: a file part and the answer, or no answer when nothing is drawn. */
    const commitDrawing = async () => {
        if (!hasInk(strokes.current)) {
            removeFile(field.id);
            removeAnswer(field.id);
            return;
        }
        const canvas = canvasRef.current;
        const blob = canvas ? await canvasToPng(canvas) : null;
        if (!blob) {
            setPadUnavailable(true);
            return;
        }
        const fileId = v4();
        addFile(field.id, fileId, SIGNATURE_FILE_NAME, new File([blob], SIGNATURE_FILE_NAME, { type: 'image/png' }));
        addFieldSignatureAnswer(field.id, { method: 'drawn', file_id: fileId });
        setStatus(t('SIGNATURE.ADDED'));
    };

    const down = (event: React.PointerEvent<HTMLCanvasElement>) => {
        if (isBuilder || (event.pointerType === 'mouse' && event.button !== 0)) return;
        const rect = event.currentTarget.getBoundingClientRect();
        drawing.current = true;
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
        if (!drawing.current) return;
        const rect = event.currentTarget.getBoundingClientRect();
        strokes.current = extendStroke(strokes.current, pointFrom(rect, event.clientX, event.clientY));
        repaint();
    };
    const up = () => {
        if (!drawing.current) return;
        drawing.current = false;
        void commitDrawing();
    };

    const clear = () => {
        strokes.current = [];
        setInked(false);
        removeFile(field.id);
        removeAnswer(field.id);
        setStatus(t('SIGNATURE.CLEARED'));
        repaint();
    };

    const choose = (next: Method) => {
        if (isBuilder || next === method) return;
        setMethod(next);
        setStatus('');
        if (next === 'typed') {
            // the drawing is set aside (kept on the page, not sent) while a name is typed
            removeFile(field.id);
            const name = normalisedName(draft);
            if (name) addFieldSignatureAnswer(field.id, { method: 'typed', name });
            else removeAnswer(field.id);
        } else {
            removeAnswer(field.id);
            if (hasInk(strokes.current)) window.setTimeout(() => void commitDrawing(), 0);
        }
    };

    const typedName = normalisedName(draft);
    const badName = draft.trim() !== '' && typedName === undefined;
    const type = (value: string) => {
        setDraft(value);
        const name = normalisedName(value);
        if (name) {
            addFieldSignatureAnswer(field.id, { method: 'typed', name });
            setStatus('');
        } else if (value.trim()) {
            // a name with characters that cannot be used is kept as typed, so the page flags it and never sends it (as an impossible day is)
            addFieldSignatureAnswer(field.id, { method: 'typed', name: value.trim() });
        } else removeAnswer(field.id);
    };

    const radioLabelClass = (active: boolean) =>
        cn('flex min-h-11 flex-1 cursor-pointer items-center justify-center rounded border px-4 py-2 text-base font-medium has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2', active ? 'bg-white' : 'bg-transparent');
    const border = theme?.tertiary ?? '#818CA0';
    const radios: Array<{ value: Method; label: string }> = [
        { value: 'drawn', label: t('SIGNATURE.DRAW') },
        { value: 'typed', label: t('SIGNATURE.TYPE') }
    ];

    return (
        <div className="flex flex-col gap-3">
            <div role="radiogroup" aria-labelledby={question?.labelledBy} aria-label={question?.labelledBy ? undefined : t('SIGNATURE.METHOD')} aria-describedby={group['aria-describedby']} className="flex flex-wrap gap-2">
                {radios.map((radio) => (
                    <label key={radio.value} className={radioLabelClass(method === radio.value)} style={{ borderColor: method === radio.value ? (theme?.primary ?? border) : border, color: theme?.primary, borderWidth: method === radio.value ? 2 : 1 }}>
                        <input type="radio" name={`signature-method-${field.id}`} value={radio.value} checked={method === radio.value} disabled={isBuilder} onChange={() => choose(radio.value)} className="sr-only" />
                        {radio.label}
                    </label>
                ))}
            </div>

            {method === 'drawn' ? (
                <div className="flex flex-col gap-2">
                    <div className="relative w-full overflow-hidden rounded border-2 bg-white" style={{ borderColor: '#667085', aspectRatio: `${PAD_WIDTH} / ${PAD_HEIGHT}`, borderRadius: 6 }}>
                        <canvas
                            ref={canvasRef}
                            role="img"
                            aria-label={t('SIGNATURE.PAD_LABEL')}
                            aria-describedby={hintId}
                            width={PAD_WIDTH * PAD_SCALE}
                            height={PAD_HEIGHT * PAD_SCALE}
                            className={cn('absolute inset-0 h-full w-full', showHeld && 'invisible')}
                            style={{ touchAction: 'none', cursor: isBuilder ? 'default' : 'crosshair', userSelect: 'none' }}
                            onPointerDown={down}
                            onPointerMove={move}
                            onPointerUp={up}
                            onPointerCancel={up}
                            onLostPointerCapture={up}
                        />
                        {showHeld && (
                            // a local preview of the drawing this browser holds (a blob address): next/image has nothing to optimise
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={heldUrl} alt={t('SIGNATURE.DRAWN_ALT')} className="absolute inset-0 h-full w-full object-contain" />
                        )}
                        {!inked && !showHeld && (
                            <span aria-hidden="true" className="pointer-events-none absolute inset-0 flex items-end p-3 text-sm" style={{ color: '#667085' }}>
                                <span className="w-full border-b border-dashed pb-1" style={{ borderColor: '#98A2B3' }}>
                                    {t('SIGNATURE.SIGN_HERE')}
                                </span>
                            </span>
                        )}
                    </div>
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
                        maxLength={SIGNATURE_NAME_MAX}
                        value={draft}
                        disabled={isBuilder}
                        aria-labelledby={undefined}
                        aria-describedby={joinIds(control['aria-describedby'], badName && errorId)}
                        $formTheme={theme}
                        onChange={(event: React.ChangeEvent<HTMLInputElement>) => type(event.target.value)}
                        onKeyDown={onKeyDown}
                        className="min-h-12"
                    />
                    {typedName && (
                        // What the typed name will look like where it is shown: the text is the signature, the style only a flourish.
                        <p aria-hidden="true" className="m-0 overflow-hidden border-b px-1 pt-2 pb-1 text-3xl [overflow-wrap:anywhere] italic" style={{ fontFamily: TYPED_SIGNATURE_FONT, borderColor: '#98A2B3', color: '#111827' }}>
                            {typedName}
                        </p>
                    )}
                    <p id={hintId} className="m-0 text-sm text-[#667085]">
                        {t('SIGNATURE.NAME_HINT')}
                    </p>
                    {badName && (
                        <p id={errorId} className="m-0 text-[15px] leading-snug font-medium" style={{ color: theme?.primary }}>
                            {t('RULE.FORMAT_SIGNATURE')}
                        </p>
                    )}
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
