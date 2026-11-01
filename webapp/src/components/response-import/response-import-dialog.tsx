'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@app/shadcn/components/ui/dialog';
import { Progress } from '@app/shadcn/components/ui/progress';
import { useAppDispatch } from '@app/store/hooks';
import {
    ResponseImportDto,
    ResponseImportTarget,
    SUBMISSION_TAG,
    useCheckResponseImportMutation,
    useDiscardResponseImportMutation,
    useGetResponseImportQuery,
    useGetResponseImportsQuery,
    useRollbackResponseImportMutation,
    useRunResponseImportMutation,
    useUploadResponseImportMutation,
    workspacesApi
} from '@app/store/workspaces/api';
import { utcToLocalDateTimeIn } from '@app/utils/date-utils';
import { BUSY, IMPORT_MAX_MB, IMPORT_MAX_ROWS, IMPORT_POLL_MS, WAITING, cleanMapping, importFileTooLarge, mapsAQuestion, problemPlace, refusalKey, takenTargets } from '@app/utils/response-import';

type Step = 'upload' | 'map' | 'checking' | 'review' | 'running' | 'result';
const STEPS: Array<{ key: Step[]; label: string }> = [
    { key: ['upload'], label: 'STEP_UPLOAD' },
    { key: ['map'], label: 'STEP_MAP' },
    { key: ['checking', 'review'], label: 'STEP_CHECK' },
    { key: ['running', 'result'], label: 'STEP_RESULT' }
];

interface Props {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    workspaceId: string;
    formId: string;
}

type Message = { key: string; values?: Record<string, unknown> };

/**
 * Import responses from a CSV file, in five steps: the file, the matching of
 * its columns to the form's questions, a dry run that stores nothing, the import
 * (a background job with progress) and its result, which can be undone for a
 * while. The server does the work (docs/response-import.md); this only drives it.
 */
export default function ResponseImportDialog({ open, onOpenChange, workspaceId, formId }: Props) {
    const { t, i18n } = useTranslation();
    const text = useCallback((key: string, values?: Record<string, unknown>) => t(`RESPONSE_IMPORT.${key}`, values as any) as string, [t]);
    const dispatch = useAppDispatch();
    const input = useRef<HTMLInputElement>(null);
    const [step, setStep] = useState<Step>('upload');
    const [imp, setImp] = useState<ResponseImportDto | undefined>();
    const [mapping, setMapping] = useState<Record<string, string>>({});
    const [skipInvalid, setSkipInvalid] = useState(false);
    const [confirmed, setConfirmed] = useState(false);
    const [message, setMessage] = useState<Message | undefined>();
    const [dragging, setDragging] = useState(false);
    const [undoAsk, setUndoAsk] = useState(false);
    const [adoptId, setAdoptId] = useState<string | undefined>();
    const adopted = useRef(false);
    // when the check or the import was started: an answer cached from before is not its progress
    const startedAt = useRef(0);

    const [upload, { isLoading: uploading }] = useUploadResponseImportMutation();
    const [check, { isLoading: starting }] = useCheckResponseImportMutation();
    const [run, { isLoading: running }] = useRunResponseImportMutation();
    const [rollback, { isLoading: undoing }] = useRollbackResponseImportMutation();
    const [discard] = useDiscardResponseImportMutation();

    // an import of this person's that is still open, from before a reload
    const { data: recent } = useGetResponseImportsQuery({ workspaceId, formId }, { skip: !open || !workspaceId || !formId, refetchOnMountOrArgChange: true });
    useEffect(() => {
        if (!open || adopted.current || !recent || step !== 'upload' || imp) return;
        const mine = recent.find((row) => row.byMe && (WAITING.has(row.status) || BUSY.has(row.status)));
        if (mine) {
            adopted.current = true;
            setAdoptId(mine.id);
        }
    }, [open, recent, step, imp]);

    const followed = step === 'checking' || step === 'running';
    const importId = imp?.id ?? adoptId;
    const { data: polled, fulfilledTimeStamp } = useGetResponseImportQuery(
        { workspaceId, formId, importId: importId ?? '' },
        { skip: !open || !importId || !(followed || adoptId), pollingInterval: followed ? IMPORT_POLL_MS : 0, refetchOnMountOrArgChange: true }
    );

    useEffect(() => {
        if (!polled || polled.id !== importId) return;
        if (!adoptId && followed && (fulfilledTimeStamp ?? 0) < startedAt.current) return;
        setImp(polled);
        if (adoptId && polled.id === adoptId) {
            setAdoptId(undefined);
            setMapping(polled.mapping);
            setSkipInvalid(!!polled.options?.skipInvalidRows);
            if (polled.status === 'uploaded') setStep('map');
            else if (polled.status === 'checked') setStep('review');
            else if (polled.status === 'checking') setStep('checking');
            else if (polled.status === 'queued' || polled.status === 'running') setStep('running');
            return;
        }
        if (step === 'checking') {
            if (polled.status === 'checked') setStep('review');
            else if (!BUSY.has(polled.status)) setStep('result');
        } else if (step === 'running' && !BUSY.has(polled.status)) {
            setStep('result');
            dispatch(workspacesApi.util.invalidateTags([SUBMISSION_TAG]));
        }
    }, [polled, importId, adoptId, step, dispatch, followed, fulfilledTimeStamp]);

    const reset = () => {
        setStep('upload');
        setImp(undefined);
        setMapping({});
        setSkipInvalid(false);
        setConfirmed(false);
        setMessage(undefined);
        setUndoAsk(false);
        setAdoptId(undefined);
        adopted.current = false;
    };

    const close = (next: boolean) => {
        if (uploading) return;
        if (!next) {
            // a file nobody will use is thrown away at once, not left for its hour
            if (imp && WAITING.has(imp.status) && step !== 'result') discard({ workspaceId, formId, importId: imp.id });
            if (imp?.status === 'completed' || imp?.status === 'rolled_back') dispatch(workspacesApi.util.invalidateTags([SUBMISSION_TAG]));
            reset();
        }
        onOpenChange(next);
    };

    const choose = async (file: File | undefined | null) => {
        if (!file || uploading) return;
        setMessage(undefined);
        if (importFileTooLarge(file)) {
            setMessage({ key: 'ERROR_too_large', values: { mb: IMPORT_MAX_MB } });
            return;
        }
        const result = await upload({ workspaceId, formId, file });
        if ('data' in result && result.data) {
            setImp(result.data);
            setMapping(result.data.mapping);
            setStep('map');
            return;
        }
        setMessage(refusalKey('error' in result ? result.error : undefined));
    };

    const targets: ResponseImportTarget[] = imp?.targets ?? [];
    const usable = targets.filter((target) => target.status === 'ok');
    const label = (target: ResponseImportTarget) => (target.key === 'submitted_at' ? text('TARGET_SUBMITTED_AT') : target.kind === 'internal' ? text('TARGET_INTERNAL', { label: target.label }) : target.label);

    const startCheck = async () => {
        if (!imp) return;
        setMessage(undefined);
        const result = await check({ workspaceId, formId, importId: imp.id, mapping: cleanMapping(mapping), skipInvalidRows: skipInvalid });
        if ('data' in result && result.data) {
            setImp(result.data);
            startedAt.current = Date.now();
            setStep('checking');
            return;
        }
        setMessage(refusalKey('error' in result ? result.error : undefined));
    };

    const startRun = async () => {
        if (!imp) return;
        setMessage(undefined);
        const result = await run({ workspaceId, formId, importId: imp.id, mapping: cleanMapping(mapping), skipInvalidRows: skipInvalid, confirmedLawfulBasis: confirmed });
        if ('data' in result && result.data) {
            setImp(result.data);
            startedAt.current = Date.now();
            setStep('running');
            return;
        }
        setMessage(refusalKey('error' in result ? result.error : undefined));
    };

    const startUndo = async () => {
        if (!imp) return;
        const result = await rollback({ workspaceId, formId, importId: imp.id });
        setUndoAsk(false);
        if ('data' in result && result.data) {
            setImp(result.data);
            return;
        }
        setMessage(refusalKey('error' in result ? result.error : undefined));
    };

    const stepIndex = STEPS.findIndex((s) => s.key.includes(step));
    const done = imp ? Math.min(imp.progress, imp.rowCount) : 0;
    const percent = imp && imp.rowCount ? Math.round((done / imp.rowCount) * 100) : 0;
    const importable = (imp?.rowsValid ?? 0) > 0 && (skipInvalid || (imp?.rowsInvalid ?? 0) === 0);

    const problems = useMemo(() => imp?.problems ?? [], [imp]);

    return (
        <Dialog open={open} onOpenChange={close}>
            <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto bg-white" title={text('TITLE')}>
                <DialogHeader>
                    <DialogTitle>{text('TITLE')}</DialogTitle>
                    <DialogDescription>{text('DESCRIPTION')}</DialogDescription>
                </DialogHeader>
                <ol aria-label={text('STEPS_LABEL')} className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                    {STEPS.map((s, index) => (
                        <li key={s.label} aria-current={index === stepIndex ? 'step' : undefined} className={index === stepIndex ? 'font-semibold text-black-900' : index < stepIndex ? 'text-black-700' : 'text-black-500'}>
                            {index + 1}. {text(s.label)}
                        </li>
                    ))}
                </ol>

                {step === 'upload' && (
                    <div className="flex flex-col gap-3">
                        <button
                            type="button"
                            onClick={() => input.current?.click()}
                            onDragOver={(e) => {
                                e.preventDefault();
                                setDragging(true);
                            }}
                            onDragLeave={() => setDragging(false)}
                            onDrop={(e) => {
                                e.preventDefault();
                                setDragging(false);
                                choose(e.dataTransfer.files?.[0]);
                            }}
                            disabled={uploading}
                            aria-describedby="ri-limits"
                            className={`flex h-32 w-full flex-col items-center justify-center rounded-lg border-2 border-dashed px-3 text-center text-sm transition ${dragging ? 'border-brand-500 bg-brand-100' : 'border-black-300 hover:border-brand-500'}`}
                        >
                            <span className="font-medium text-black-800">{uploading ? text('UPLOADING') : text('CHOOSE_FILE')}</span>
                            {!uploading && <span className="mt-1 text-xs text-black-600">{text('DROP_HINT')}</span>}
                        </button>
                        <input ref={input} type="file" accept=".csv,text/csv,text/plain" className="hidden" tabIndex={-1} aria-hidden data-testid="ri-file-input" onChange={(e) => choose(e.target.files?.[0])} />
                        <p id="ri-limits" className="text-xs text-black-600">
                            {text('LIMITS', { mb: IMPORT_MAX_MB, rows: IMPORT_MAX_ROWS.toLocaleString(i18n.language) })}
                        </p>
                        <p className="text-xs text-black-600">{text('FORMAT_HINT')}</p>
                        {recent && recent.length > 0 && (
                            <section aria-labelledby="ri-recent" className="flex flex-col gap-1">
                                <h3 id="ri-recent" className="text-sm font-medium text-black-800">
                                    {text('RECENT')}
                                </h3>
                                <ul className="flex flex-col gap-1 text-sm text-black-700">
                                    {recent
                                        .filter((row) => row.status !== 'expired')
                                        .slice(0, 5)
                                        .map((row) => (
                                            <li key={row.id} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                                                <span className="font-medium">{text(`STATUS_${row.status}`)}</span>
                                                <span>{text('RECENT_ROW', { rows: row.rowsImported ?? row.rowCount, time: row.createdAt ? utcToLocalDateTimeIn(row.createdAt, i18n.language) : '' })}</span>
                                                {row.canRollback && (
                                                    <Button
                                                        variant="v2Button"
                                                        size="sm"
                                                        onClick={() => {
                                                            setImp(row);
                                                            setStep('result');
                                                        }}
                                                    >
                                                        {text('UNDO')}
                                                    </Button>
                                                )}
                                            </li>
                                        ))}
                                </ul>
                            </section>
                        )}
                    </div>
                )}

                {step === 'map' && imp && (
                    <div className="flex flex-col gap-3">
                        <h3 className="text-base font-semibold text-black-900">{text('MAP_TITLE')}</h3>
                        <p className="text-sm text-black-700">
                            {text('FILE_FACTS', { rows: imp.rowCount, columns: imp.columnCount })} · {text('MAP_HELP')}
                        </p>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-sm">
                                <thead>
                                    <tr className="border-b border-black-300 text-xs text-black-600">
                                        <th scope="col" className="py-1 pr-3 font-medium">
                                            {text('COLUMN_HEADER')}
                                        </th>
                                        <th scope="col" className="py-1 font-medium">
                                            {text('TARGET_HEADER')}
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {imp.headers.map((header, index) => {
                                        const taken = takenTargets(mapping, String(index));
                                        const heading = header || text('COLUMN_FALLBACK', { n: index + 1 });
                                        const note = imp.notes.find((n) => n.column === index);
                                        return (
                                            <tr key={index} className="border-b border-black-200 align-top">
                                                <th scope="row" className="max-w-[16rem] py-2 pr-3 font-normal break-words text-black-900">
                                                    {heading}
                                                    {note && <span className="mt-0.5 block text-xs text-black-600">{text(`NOTE_${note.code}`)}</span>}
                                                </th>
                                                <td className="py-2">
                                                    <select
                                                        aria-label={`${text('TARGET_HEADER')}: ${heading}`}
                                                        value={mapping[String(index)] ?? ''}
                                                        onChange={(e) => setMapping({ ...mapping, [String(index)]: e.target.value })}
                                                        className="w-full max-w-sm rounded border border-black-300 bg-white px-2 py-1.5 text-sm"
                                                    >
                                                        <option value="">{text('NOT_IMPORTED')}</option>
                                                        {usable.map((target) => (
                                                            <option key={target.key} value={target.key} disabled={taken.has(target.key)}>
                                                                {label(target)}
                                                            </option>
                                                        ))}
                                                    </select>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                        <label className="flex items-start gap-2 text-sm text-black-800">
                            <input type="checkbox" checked={skipInvalid} onChange={(e) => setSkipInvalid(e.target.checked)} className="mt-1" />
                            <span>
                                {text('SKIP_INVALID')}
                                <span className="block text-xs text-black-600">{text('SKIP_INVALID_HELP')}</span>
                            </span>
                        </label>
                    </div>
                )}

                {step === 'checking' && imp && (
                    <div role="status" aria-live="polite" className="flex flex-col gap-2">
                        <p className="text-sm font-medium text-black-900">{text('CHECKING')}</p>
                        <Progress value={percent} className="bg-black-200" aria-label={text('CHECKING')} />
                        <p className="text-xs text-black-600">{text('CHECKING_PROGRESS', { done, total: imp.rowCount })}</p>
                    </div>
                )}

                {step === 'review' && imp && (
                    <div className="flex flex-col gap-3">
                        <h3 className="text-base font-semibold text-black-900">{text('CHECK_TITLE')}</h3>
                        <p role="status" className="text-sm text-black-800">
                            {(imp.rowsInvalid ?? 0) === 0 ? text('ALL_VALID', { count: imp.rowsValid ?? 0 }) : `${text('VALID_OF', { valid: imp.rowsValid ?? 0, total: imp.rowCount })} ${text('SOME_INVALID', { count: imp.rowsInvalid ?? 0 })}`}
                        </p>
                        <ProblemList imp={imp} problems={problems} text={text} />
                        {importable && (
                            <label className="flex items-start gap-2 text-sm text-black-800">
                                <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} className="mt-1" />
                                <span>
                                    {text('CONFIRM')}
                                    <span className="block text-xs text-black-600">{text('CONFIRM_HELP')}</span>
                                </span>
                            </label>
                        )}
                    </div>
                )}

                {step === 'running' && imp && (
                    <div role="status" aria-live="polite" className="flex flex-col gap-2">
                        <p className="text-sm font-medium text-black-900">{text('IMPORTING')}</p>
                        <Progress value={percent} className="bg-black-200" aria-label={text('IMPORTING')} />
                        <p className="text-xs text-black-600">{text('CHECKING_PROGRESS', { done, total: imp.rowCount })}</p>
                        <p className="text-xs text-black-600">{text('IMPORTING_HELP')}</p>
                    </div>
                )}

                {step === 'result' && imp && (
                    <div className="flex flex-col gap-3" role="status" aria-live="polite">
                        {imp.status === 'completed' && (
                            <>
                                <h3 className="text-base font-semibold text-black-900">{text('DONE_TITLE')}</h3>
                                <p className="text-sm text-black-800">{text('DONE', { count: imp.rowsImported ?? 0 })}</p>
                                {(imp.rowsSkipped ?? 0) > 0 && <p className="text-sm text-black-800">{text('DONE_SKIPPED', { count: imp.rowsSkipped ?? 0 })}</p>}
                                <p className="text-xs text-black-600">{text('DONE_NOTHING_FIRED')}</p>
                                {imp.canRollback && imp.rollbackUntil && <p className="text-xs text-black-600">{text('UNDO_UNTIL', { time: utcToLocalDateTimeIn(imp.rollbackUntil, i18n.language) })}</p>}
                            </>
                        )}
                        {imp.status === 'rolled_back' && <p className="text-sm text-black-800">{text('UNDONE', { count: imp.rolledBackCount ?? 0 })}</p>}
                        {(imp.status === 'failed' || imp.status === 'cancelled') && (
                            <>
                                <h3 className="text-base font-semibold text-black-900">{text('FAILED_TITLE')}</h3>
                                <p className="text-sm text-red-700">{text(`ERROR_${imp.errorCode ?? 'generic'}`, { mb: IMPORT_MAX_MB, rows: IMPORT_MAX_ROWS })}</p>
                                <p className="text-xs text-black-600">{text('FAILED_NOTHING_STORED')}</p>
                                <ProblemList imp={imp} problems={problems} text={text} />
                            </>
                        )}
                        {undoAsk && (
                            <div className="flex flex-col gap-2 rounded border border-black-300 p-3">
                                <p className="text-sm text-black-900">{text('UNDO_CONFIRM', { count: imp.rowsImported ?? 0 })}</p>
                                <div className="flex gap-2">
                                    <Button variant="v2Button" onClick={() => setUndoAsk(false)}>
                                        {text('BACK')}
                                    </Button>
                                    <Button onClick={startUndo} isLoading={undoing}>
                                        {text('UNDO_YES')}
                                    </Button>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                <div role="alert" aria-live="assertive">
                    {message && <p className="text-sm text-red-700">{text(message.key, message.values)}</p>}
                </div>

                <div className="flex flex-wrap justify-end gap-2">
                    {step === 'upload' && (
                        <Button variant="v2Button" onClick={() => close(false)} disabled={uploading}>
                            {text('CLOSE')}
                        </Button>
                    )}
                    {step === 'map' && (
                        <>
                            <Button
                                variant="v2Button"
                                onClick={() => {
                                    if (imp) discard({ workspaceId, formId, importId: imp.id });
                                    reset();
                                }}
                            >
                                {text('CANCEL_UPLOAD')}
                            </Button>
                            <Button onClick={startCheck} isLoading={starting} disabled={!imp || !mapsAQuestion(mapping, targets)}>
                                {text('CHECK')}
                            </Button>
                        </>
                    )}
                    {step === 'review' && (
                        <>
                            <Button variant="v2Button" onClick={() => setStep('map')}>
                                {text('BACK')}
                            </Button>
                            <Button onClick={startRun} isLoading={running} disabled={!importable || !confirmed}>
                                {(imp?.rowsInvalid ?? 0) > 0 ? text('IMPORT_FILTERED', { count: imp?.rowsValid ?? 0 }) : text('IMPORT_ALL', { count: imp?.rowsValid ?? 0 })}
                            </Button>
                        </>
                    )}
                    {(step === 'checking' || step === 'running') && (
                        <Button variant="v2Button" onClick={() => close(false)}>
                            {text('CLOSE')}
                        </Button>
                    )}
                    {step === 'result' && (
                        <>
                            {imp?.status === 'completed' && imp.canRollback && !undoAsk && (
                                <Button variant="v2Button" onClick={() => setUndoAsk(true)}>
                                    {text('UNDO')}
                                </Button>
                            )}
                            {(imp?.status === 'failed' || imp?.status === 'cancelled') && (
                                <Button variant="v2Button" onClick={reset}>
                                    {text('START_OVER')}
                                </Button>
                            )}
                            <Button onClick={() => close(false)}>{text('CLOSE')}</Button>
                        </>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}

function ProblemList({ imp, problems, text }: { imp: ResponseImportDto; problems: ResponseImportDto['problems']; text: (key: string, values?: Record<string, unknown>) => string }) {
    if (problems.length === 0) return null;
    return (
        <section aria-labelledby="ri-problems" className="flex flex-col gap-1">
            <h4 id="ri-problems" className="text-sm font-medium text-black-900">
                {text('PROBLEMS')}
            </h4>
            <div className="max-h-64 overflow-auto rounded border border-black-300">
                <table className="w-full text-left text-sm">
                    <thead>
                        <tr className="border-b border-black-300 text-xs text-black-600">
                            <th scope="col" className="px-2 py-1 font-medium">
                                {text('PROBLEM_TABLE_ROW')}
                            </th>
                            <th scope="col" className="px-2 py-1 font-medium">
                                {text('PROBLEM_TABLE_WHERE')}
                            </th>
                            <th scope="col" className="px-2 py-1 font-medium">
                                {text('PROBLEM_TABLE_WHAT')}
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {problems.map((problem, index) => {
                            const place = problemPlace(problem, imp);
                            const where = [...new Set([place.question, place.column ?? (place.columnNumber ? text('PROBLEM_COLUMN', { column: place.columnNumber }) : undefined)].filter(Boolean))].join(' · ') || text('PROBLEM_WHOLE_ROW');
                            const known = `PROBLEM_${problem.code}`;
                            return (
                                <tr key={index} className="border-b border-black-200 align-top">
                                    <td className="px-2 py-1 whitespace-nowrap">{problem.row}</td>
                                    <td className="px-2 py-1 break-words">
                                        {where}
                                        {typeof problem.item === 'number' ? ` · ${text('PROBLEM_ITEM', { n: problem.item + 1 })}` : ''}
                                    </td>
                                    <td className="px-2 py-1">{hasKey(text, known) ? text(known) : text('PROBLEM_other', { code: problem.code })}</td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
            {imp.problemsTruncated && <p className="text-xs text-black-600">{text('PROBLEMS_TRUNCATED', { count: problems.length })}</p>}
        </section>
    );
}

/** A message that exists: i18next answers a missing key with the key itself. */
function hasKey(text: (key: string) => string, key: string): boolean {
    return text(key) !== `RESPONSE_IMPORT.${key}`;
}
