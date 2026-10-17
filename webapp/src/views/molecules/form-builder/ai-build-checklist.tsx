'use client';

import React, { useState } from 'react';

import { X } from 'lucide-react';

import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { BuildReport, clearBuildReport, findingText, readBuildReport } from '@app/utils/ai-build-report';

interface Target {
    label: string;
    slide: { id: string; index: number };
    field?: { id: string; index: number };
}

function plainTitle(title: unknown): string {
    if (typeof title === 'string') return title.trim();
    return '';
}

/** Where a finding points (question ids, page ids or page numbers), as
 * places in the form the person can go to. */
function targetsOf(where: string[], slides: any[]): Target[] {
    const targets: Target[] = [];
    const page = (slideIndex: number): Target => ({ label: `page ${slideIndex + 1}`, slide: { id: slides[slideIndex].id, index: slideIndex } });
    for (const ref of where) {
        let found: Target | null = null;
        slides.forEach((slide, slideIndex) => {
            (slide?.properties?.fields ?? []).forEach((field: any, fieldIndex: number) => {
                if (!found && field?.id === ref) {
                    const title = plainTitle(field.title);
                    const label = title ? `“${title.length > 40 ? title.slice(0, 37) + '…' : title}”` : `page ${slideIndex + 1}, question ${fieldIndex + 1}`;
                    found = { label, slide: { id: slide.id, index: slideIndex }, field: { id: field.id, index: fieldIndex } };
                }
            });
        });
        if (!found) {
            const slideIndex = slides.findIndex((slide) => slide?.id === ref);
            if (slideIndex >= 0) found = page(slideIndex);
            else if (/^\d+$/.test(ref) && Number(ref) >= 1 && Number(ref) <= slides.length) found = page(Number(ref) - 1);
        }
        const target = found as Target | null;
        if (target && !targets.some((t) => t.slide.id === target.slide.id && t.field?.id === target.field?.id)) targets.push(target);
    }
    return targets;
}

/** What building the form from an AI outline left to check, until the
 * person dismisses it. */
export default function AIBuildChecklist({ formId }: { formId: string }) {
    // mounted in the browser only (the editor waits for the form first)
    const [report, setReport] = useState<BuildReport | null>(() => readBuildReport(formId));
    if (!report) return null;
    const dismiss = () => {
        clearBuildReport(formId);
        setReport(null);
    };
    return <Checklist report={report} onDismiss={dismiss} />;
}

/** The checklist while it shows: its "Go to" links follow the form. */
function Checklist({ report, onDismiss: dismiss }: { report: BuildReport; onDismiss: () => void }) {
    const { formFields } = useFormFieldsAtom();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();

    const slides = Array.isArray(formFields) ? formFields : [];
    const go = (target: Target) => {
        setActiveSlideComponent(target.slide);
        setActiveFieldComponent(target.field ?? null);
    };

    return (
        <section aria-labelledby="ai-build-checklist-title" className="w-[min(360px,calc(100vw-2rem))] rounded-lg border border-black-300 bg-white p-4 text-sm shadow-large">
            <div className="flex items-start justify-between gap-2">
                <h2 id="ai-build-checklist-title" className="font-semibold text-black-900">
                    Check before publishing
                </h2>
                <button type="button" className="rounded p-1 text-black-600 hover:bg-black-200" aria-label="Dismiss the checklist" onClick={dismiss}>
                    <X size={16} aria-hidden="true" />
                </button>
            </div>
            <p className="mt-1 text-xs text-black-600">Your form was built from the AI outline. {report.findings.length ? 'These need a look:' : 'What changed on the way:'}</p>
            {report.findings.length > 0 && (
                <ul className="mt-2 flex flex-col gap-2">
                    {report.findings.map((finding, i) => {
                        const targets = targetsOf(finding.where, slides);
                        return (
                            <li key={`${finding.code}-${i}`} className="text-black-800">
                                <span className={finding.severity === 'error' ? 'font-medium' : undefined}>{findingText(finding.code)}</span>
                                {targets.length > 0 && (
                                    <span className="ml-1 inline-flex flex-wrap gap-x-2">
                                        {targets.map((target) => (
                                            <button key={`${target.slide.id}-${target.field?.id ?? ''}`} type="button" className="text-brand-600 underline" onClick={() => go(target)}>
                                                Go to {target.label}
                                            </button>
                                        ))}
                                    </span>
                                )}
                            </li>
                        );
                    })}
                </ul>
            )}
            {report.notes.length > 0 && (
                <ul className="mt-2 list-disc pl-4 text-xs text-black-600">
                    {report.notes.map((note) => (
                        <li key={note}>{note}</li>
                    ))}
                </ul>
            )}
        </section>
    );
}
