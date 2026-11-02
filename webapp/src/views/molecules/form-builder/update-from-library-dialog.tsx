'use client';

import { useEffect, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@app/shadcn/components/ui/dialog';
import { cn } from '@app/shadcn/util/lib';
import type { ChangeStatus, SectionChange, SectionPlan } from '@app/store/reusable-sections/api';
import { whatKey } from '@app/utils/reusable-sections';

const STATUS_ORDER: ChangeStatus[] = ['added', 'changed', 'removed', 'unchanged'];
const STATUS_STYLE: Record<ChangeStatus, string> = {
    added: 'bg-green-100 text-green-900',
    changed: 'bg-amber-100 text-amber-900',
    removed: 'bg-red-100 text-red-900',
    unchanged: 'bg-black-200 text-black-800'
};

/** Per question: what an update does to it, in the builder's words. Exported for its test. */
export function ChangeRow({ change }: { change: SectionChange }) {
    const { t } = useTranslation('builder');
    return (
        <li className="flex flex-col gap-0.5 border-t border-black-300 py-2 first:border-t-0">
            <div className="flex items-center gap-2">
                <span className={cn('shrink-0 rounded px-1.5 py-0.5 text-[11px] font-medium', STATUS_STYLE[change.status])}>{t(`SECTIONS_LIB.UPDATE.STATUS_${change.status.toUpperCase()}`)}</span>
                <span className="min-w-0 truncate text-sm text-black-900">{change.title || t('SECTIONS_LIB.UNTITLED')}</span>
            </div>
            {change.status === 'changed' && change.what.length > 0 && <p className="pl-1 text-xs text-black-700">{change.what.map((what) => t(whatKey(what))).join(', ')}</p>}
            {change.modifiedInCopy && change.status !== 'added' && <p className="pl-1 text-xs text-amber-900">{t('SECTIONS_LIB.UPDATE.MODIFIED_IN_COPY')}</p>}
        </li>
    );
}

/**
 * "Update from library": the diff of this copy against the section's newest version, then replace it. Questions
 * the copy and the library share keep their place and their id (so answers stay readable); a question whose type
 * changed is replaced by a new one. A published form changes only when the creator publishes again.
 */
export default function UpdateFromLibraryDialog({ open, onOpenChange, plan, apply }: { open: boolean; onOpenChange: (open: boolean) => void; plan: () => Promise<SectionPlan | null>; apply: (plan: SectionPlan) => boolean }) {
    const { t } = useTranslation('builder');
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent title={t('SECTIONS_LIB.UPDATE.TITLE')} className="max-w-lg">
                <DialogHeader>
                    <DialogTitle>{t('SECTIONS_LIB.UPDATE.TITLE')}</DialogTitle>
                    <DialogDescription>{t('SECTIONS_LIB.UPDATE.INTRO')}</DialogDescription>
                </DialogHeader>
                {/* mounted only while open, so every opening compares afresh */}
                <UpdatePlan loadPlan={plan} onOpenChange={onOpenChange} apply={apply} />
            </DialogContent>
        </Dialog>
    );
}

function UpdatePlan({ loadPlan, onOpenChange, apply }: { loadPlan: () => Promise<SectionPlan | null>; onOpenChange: (open: boolean) => void; apply: (plan: SectionPlan) => boolean }) {
    const { t } = useTranslation('builder');
    const [plan, setPlan] = useState<SectionPlan | null>(null);

    useEffect(() => {
        let current = true;
        loadPlan().then((found) => {
            if (!current) return;
            if (found) setPlan(found);
            else onOpenChange(false);
        });
        return () => {
            current = false;
        };
        // the plan is read once, when the dialog opens
    }, []);

    const counts = (status: ChangeStatus) => plan?.changes.filter((change) => change.status === status).length ?? 0;
    const nothing = !!plan && plan.changes.every((change) => change.status === 'unchanged');
    const ordered = plan ? [...plan.changes].sort((a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status)) : [];
    if (!plan) {
        return (
            <p role="status" className="text-sm text-black-600">
                {t('SECTIONS_LIB.UPDATE.LOADING')}
            </p>
        );
    }
    return (
        <div className="flex flex-col gap-3">
            <p className="text-sm text-black-800">{nothing ? t('SECTIONS_LIB.UPDATE.UP_TO_DATE') : t('SECTIONS_LIB.UPDATE.SUMMARY', { version: plan.version, added: counts('added'), changed: counts('changed'), removed: counts('removed') })}</p>
            {!plan.baseKnown && <p className="text-xs text-black-600">{t('SECTIONS_LIB.UPDATE.BASE_UNKNOWN')}</p>}
            <ul className="max-h-[40vh] overflow-y-auto pr-1" aria-label={t('SECTIONS_LIB.UPDATE.LIST')}>
                {ordered.map((change) => (
                    <ChangeRow key={`${change.key}-${change.status}`} change={change} />
                ))}
            </ul>
            <p className="text-xs text-black-600">{t('SECTIONS_LIB.UPDATE.NOTE')}</p>
            <div className="flex justify-end gap-2">
                <Button type="button" variant="secondary" className="min-h-11" onClick={() => onOpenChange(false)}>
                    {t('SECTIONS_LIB.CANCEL')}
                </Button>
                <Button
                    type="button"
                    className="min-h-11"
                    onClick={() => {
                        if (apply(plan)) onOpenChange(false);
                    }}
                >
                    {t('SECTIONS_LIB.UPDATE.APPLY')}
                </Button>
            </div>
        </div>
    );
}
