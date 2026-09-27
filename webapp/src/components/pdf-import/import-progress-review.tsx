'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';

import Link from 'next/link';

import { Button } from '@app/shadcn/components/ui/button';
import { pageImageUrl, useGetPdfImportQuery, useGetPdfImportReviewQuery } from '@app/store/redux/pdf-import-api';
import { STAGES, describeRules, placeBox, progressPercent, stageStates } from '@app/utils/pdf-import';

const POLL_MS = 2000;

function StageList({ states }: { states: Record<string, string> }) {
    return (
        <ol className="flex flex-col gap-2">
            {STAGES.map((s) => (
                <li key={s.key} className="flex items-center gap-3 text-sm">
                    <span aria-hidden className={`h-2.5 w-2.5 rounded-full ${states[s.key] === 'done' ? 'bg-green-600' : states[s.key] === 'current' ? 'animate-pulse bg-blue-500' : states[s.key] === 'failed' ? 'bg-red-600' : 'bg-black-300'}`} />
                    <span className={states[s.key] === 'waiting' ? 'text-black-500' : 'text-black-800'}>{s.label}</span>
                </li>
            ))}
        </ol>
    );
}

function PageWithBoxes({ workspaceId, importId, page, selected, onSelect }: any) {
    const holder = useRef<HTMLDivElement>(null);
    const [width, setWidth] = useState(0);
    useEffect(() => {
        const el = holder.current;
        if (!el) return;
        const observer = new ResizeObserver(() => setWidth(el.clientWidth));
        observer.observe(el);
        setWidth(el.clientWidth);
        return () => observer.disconnect();
    }, []);
    const height = page.width ? (width * page.height) / page.width : 0;
    return (
        <div ref={holder} className="relative w-full overflow-hidden rounded-md border border-black-200 bg-white" style={{ height: height || undefined }}>
            {page.has_image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={pageImageUrl(workspaceId, importId, page.number)} alt={`Page ${page.number} of the uploaded document`} className="block w-full" />
            ) : (
                <div className="flex h-full min-h-40 items-center justify-center p-6 text-center text-sm text-black-500">No page image (the document reader for images is not configured on this server).</div>
            )}
            {width > 0 &&
                page.boxes.map((b: any) => {
                    const pos = placeBox(b.bbox, page.width, width);
                    const isSelected = selected === b.id;
                    return (
                        <button
                            key={b.id}
                            type="button"
                            title={b.label}
                            onClick={() => onSelect(b.id)}
                            className={`absolute rounded-sm border-2 ${b.type === 'staff_only' ? 'border-amber-500 bg-amber-500/10' : (b.confidence ?? 1) < 0.5 ? 'border-orange-500 bg-orange-500/10' : 'border-blue-500 bg-blue-500/10'} ${isSelected ? 'ring-2 ring-blue-700' : ''}`}
                            style={pos}
                        />
                    );
                })}
        </div>
    );
}

export default function ImportProgressReview({ workspaceId, workspaceName, importId }: { workspaceId: string; workspaceName: string; importId: string }) {
    const [finished, setFinished] = useState(false);
    const { data } = useGetPdfImportQuery({ workspaceId, importId }, { pollingInterval: finished ? 0 : POLL_MS, skip: !workspaceId });
    const done = data?.status === 'completed' || data?.status === 'failed';
    useEffect(() => {
        if (done) setFinished(true);
    }, [done]);
    const { data: review } = useGetPdfImportReviewQuery({ workspaceId, importId }, { skip: !workspaceId || data?.status !== 'completed' });
    const [selected, setSelected] = useState<string | null>(null);

    const finishedStages = useMemo(() => data?.finishedStages ?? [], [data]);
    const states = stageStates(data?.status ?? 'queued', data?.stage, finishedStages);
    const report = review?.report ?? data?.report ?? {};
    const compile = report.compile ?? {};
    const rules = describeRules(compile.rules);

    if (!data) return <div className="p-10 text-sm text-black-600">Loading…</div>;

    if (data.status !== 'completed') {
        return (
            <div className="mx-auto flex max-w-xl flex-col gap-6 p-10">
                <div>
                    <h1 className="h3-new text-black-800">Importing {data.fileName}</h1>
                    <p className="mt-1 text-sm text-black-600">{data.status === 'failed' ? 'The import stopped.' : 'This usually takes under a minute. You can leave this page; the draft form will be ready in your forms list.'}</p>
                </div>
                {data.status !== 'failed' && (
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-black-200">
                        <div className="h-full bg-blue-500 transition-all" style={{ width: `${progressPercent(states)}%` }} />
                    </div>
                )}
                <StageList states={states} />
                {data.error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{data.error}</p>}
                {data.status === 'failed' && (
                    <Link href={`/${workspaceName}/dashboard/forms/create`}>
                        <Button variant="v2Button">Try another file</Button>
                    </Link>
                )}
            </div>
        );
    }

    const selectedBox = review?.pages.flatMap((p) => p.boxes).find((b) => b.id === selected);
    return (
        <div className="mx-auto flex max-w-[1330px] flex-col gap-6 p-6 md:p-10 lg:flex-row">
            <div className="flex w-full flex-col gap-4 lg:w-3/5">
                <p className="text-sm text-black-600">
                    Each outlined area became a question in your draft. <span className="text-orange-600">Orange</span> means the reading was uncertain; <span className="text-amber-600">amber</span> marks staff-only parts.
                </p>
                {review?.pages.map((page) => (
                    <div key={page.number} className="flex flex-col gap-1">
                        <span className="text-xs text-black-600">Page {page.number}</span>
                        <PageWithBoxes workspaceId={workspaceId} importId={importId} page={page} selected={selected} onSelect={setSelected} />
                    </div>
                ))}
            </div>
            <aside className="flex w-full flex-col gap-5 lg:sticky lg:top-6 lg:w-2/5 lg:self-start">
                <div>
                    <h1 className="h3-new text-black-800">Your draft is ready</h1>
                    <p className="mt-1 text-sm text-black-600">
                        {compile.fields ?? 0} fields on {compile.pages ?? 0} pages from {data.pageCount ?? 0} page{data.pageCount === 1 ? '' : 's'} of {data.fileName}. Review it in the builder before publishing.
                    </p>
                </div>
                <Link href={`/${workspaceName}/dashboard/forms/${data.formId}/edit`}>
                    <Button className="w-full">Open in builder</Button>
                </Link>
                {selectedBox && (
                    <div className="rounded-md border border-black-200 p-3 text-sm">
                        <div className="font-medium text-black-800">{selectedBox.label || 'Untitled'}</div>
                        <div className="text-xs text-black-600">{selectedBox.type === 'staff_only' ? 'Staff-only part' : selectedBox.kind?.replace(/_/g, ' ')}</div>
                    </div>
                )}
                {rules.length > 0 && (
                    <section>
                        <h2 className="mb-2 text-sm font-semibold text-black-800">What we changed</h2>
                        <ul className="list-disc space-y-1 pl-5 text-sm text-black-700">
                            {rules.map((r) => (
                                <li key={r}>{r}</li>
                            ))}
                        </ul>
                    </section>
                )}
                {(compile.staff_only?.length ?? 0) > 0 && (
                    <section>
                        <h2 className="mb-2 text-sm font-semibold text-black-800">Set aside for staff</h2>
                        <ul className="list-disc space-y-1 pl-5 text-sm text-black-700">
                            {compile.staff_only.map((s: any) => (
                                <li key={s.element}>{s.heading || 'Staff-only part'} — not shown to respondents</li>
                            ))}
                        </ul>
                    </section>
                )}
                {((compile.dropped?.length ?? 0) > 0 || (compile.interim?.length ?? 0) > 0) && (
                    <section>
                        <h2 className="mb-2 text-sm font-semibold text-black-800">Worth a look</h2>
                        <ul className="list-disc space-y-1 pl-5 text-sm text-black-700">
                            {(compile.dropped ?? []).map((d: any) => (
                                <li key={d.element}>
                                    {d.label || 'An item'}: {d.reason}
                                </li>
                            ))}
                            {(compile.interim ?? []).map((i: any) => (
                                <li key={i.element}>
                                    {i.label || 'A table'} was imported as {i.as}.
                                </li>
                            ))}
                        </ul>
                    </section>
                )}
                {(report.notes ?? []).length > 0 && (
                    <section className="text-xs text-black-600">
                        {report.notes.map((n: string) => (
                            <p key={n}>{n}</p>
                        ))}
                    </section>
                )}
            </aside>
        </div>
    );
}
