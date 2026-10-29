'use client';

import React from 'react';

import { useTranslation } from 'react-i18next';

import type { ImportReportItem } from '@app/store/redux/open-formulieren-import-api';
import { groupReport, reportLabelOf, reportSentenceOf } from '@app/utils/open-formulieren-import';

const ROOT = 'OPEN_FORMULIEREN_IMPORT';
const DETAIL_NAMES = ['componentType', 'property', 'actionType', 'plugin', 'dataType', 'operator', 'source', 'rules'];

/** Translate a key below OPEN_FORMULIEREN_IMPORT (builder namespace). */
export function useImportText() {
    const { t } = useTranslation('builder');
    return (key: string, values?: Record<string, string | number>) => t(`${ROOT}.${key}`, values as any) as unknown as string;
}

/** The sentence for an item. Everything comes back as a plain string: callers render it as text. */
export function useReportSentence() {
    const text = useImportText();
    return (item: ImportReportItem) => {
        const { key, values } = reportSentenceOf(item);
        // a detail the server left out reads as "unknown", never as a bare placeholder
        const withDefaults: Record<string, string | number> = { ...Object.fromEntries(DETAIL_NAMES.map((name) => [name, text('DETAIL_UNKNOWN')])), ...values };
        if (withDefaults.key === undefined) withDefaults.key = text('DETAIL_UNKNOWN');
        return text(key, withDefaults);
    };
}

function Marker({ severity }: { severity?: string | null }) {
    const text = useImportText();
    const warning = severity === 'warning';
    return (
        <>
            <span aria-hidden className={`mt-[7px] h-2 w-2 shrink-0 rounded-full ${warning ? 'bg-amber-500' : 'bg-black-400'}`} />
            <span className="sr-only">{warning ? text('REPORT.WARNING') : text('REPORT.INFO')}: </span>
        </>
    );
}

/**
 * One list item per report item: its label, the page it is on, and a sentence
 * built from the reason code and detail. The label and every value from the
 * server are rendered as text, never as HTML.
 */
export function ReportItem({ item }: { item: ImportReportItem }) {
    const text = useImportText();
    const sentence = useReportSentence();
    const label = reportLabelOf(item);
    const hasStep = typeof item.step === 'number' && Number.isFinite(item.step) && item.step >= 0;
    return (
        <li className="flex gap-2.5 text-sm text-black-800">
            <Marker severity={item.severity} />
            <div className="min-w-0">
                {(label || hasStep) && (
                    <div className="flex flex-wrap items-baseline gap-x-2">
                        {label && <span className="font-medium break-words">{label}</span>}
                        {hasStep && <span className="text-xs text-black-600">{text('REPORT.PAGE', { number: (item.step as number) + 1 })}</span>}
                    </div>
                )}
                <p className="text-black-700">{sentence(item)}</p>
            </div>
        </li>
    );
}

/** The report's items under a heading per outcome, the ones to check first. */
export function ReportItemGroups({ items, headingLevel = 2 }: { items: ReadonlyArray<ImportReportItem>; headingLevel?: 2 | 3 }) {
    const text = useImportText();
    const Heading = (headingLevel === 2 ? 'h2' : 'h3') as 'h2';
    return (
        <>
            {groupReport(items).map((group) => (
                <section key={group.code} aria-labelledby={`oof-group-${group.code}`}>
                    <Heading id={`oof-group-${group.code}`} className="mb-2 text-sm font-semibold text-black-800">
                        {text(`REPORT.GROUP.${group.code}`)} <span className="font-normal text-black-600">({group.items.length})</span>
                    </Heading>
                    <ul className="flex flex-col gap-3">
                        {group.items.map((item, index) => (
                            <ReportItem key={`${item.code}-${item.reason}-${item.key ?? ''}-${index}`} item={item} />
                        ))}
                    </ul>
                </section>
            ))}
        </>
    );
}
