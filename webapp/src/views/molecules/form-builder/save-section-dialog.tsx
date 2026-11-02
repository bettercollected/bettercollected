'use client';

import { FormEvent, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@app/shadcn/components/ui/dialog';
import { AppInput } from '@app/shadcn/components/ui/input';
import type { SectionDetail } from '@app/store/reusable-sections/api';
import { warningKey } from '@app/utils/reusable-sections';

/**
 * "Save as reusable section": a name and an optional description, then the library keeps the questions. What the
 * library could not keep (a rule that read a question outside the section, another form's answers) is listed once
 * the section is saved, so nothing is lost without the creator knowing.
 */
export default function SaveSectionDialog({
    open,
    onOpenChange,
    subject,
    defaultName,
    save
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    /** What is being saved, in words ("this question", "this panel"). */
    subject: string;
    defaultName?: string;
    save: (name: string, description: string) => Promise<SectionDetail | null>;
}) {
    const { t } = useTranslation('builder');
    const [name, setName] = useState(defaultName ?? '');
    const [description, setDescription] = useState('');
    const [busy, setBusy] = useState(false);
    const [saved, setSaved] = useState<SectionDetail | null>(null);

    const close = (next: boolean) => {
        onOpenChange(next);
        if (!next) setTimeout(() => setSaved(null), 200);
    };
    const submit = async (event: FormEvent) => {
        event.preventDefault();
        if (!name.trim() || busy) return;
        setBusy(true);
        const result = await save(name.trim(), description.trim());
        setBusy(false);
        if (!result) return;
        // nothing to tell: done; otherwise the creator reads what was left out first
        if (!result.warnings.length) close(false);
        else setSaved(result);
    };

    return (
        <Dialog open={open} onOpenChange={close}>
            <DialogContent title={t('SECTIONS_LIB.SAVE.TITLE')} className="max-w-md">
                <DialogHeader>
                    <DialogTitle>{t('SECTIONS_LIB.SAVE.TITLE')}</DialogTitle>
                    <DialogDescription>{saved ? t('SECTIONS_LIB.SAVE.SAVED', { name: saved.name }) : t('SECTIONS_LIB.SAVE.INTRO', { subject })}</DialogDescription>
                </DialogHeader>
                {saved ? (
                    <div className="flex flex-col gap-3">
                        <p className="text-sm font-medium text-black-900">{t('SECTIONS_LIB.SAVE.LEFT_OUT')}</p>
                        <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm text-black-800">
                            {saved.warnings.map((warning, index) => (
                                <li key={`${warning.code}-${warning.fieldId}-${index}`}>{t(warningKey(warning.code), { title: warning.title || t('SECTIONS_LIB.UNTITLED') })}</li>
                            ))}
                        </ul>
                        <Button type="button" className="min-h-11 self-end" onClick={() => close(false)}>
                            {t('SECTIONS_LIB.SAVE.DONE')}
                        </Button>
                    </div>
                ) : (
                    <form className="flex flex-col gap-3" onSubmit={submit}>
                        <label className="flex flex-col gap-1 text-sm text-black-800">
                            {t('SECTIONS_LIB.SAVE.NAME')}
                            <AppInput value={name} maxLength={100} onChange={(event: any) => setName(event.target.value)} placeholder={t('SECTIONS_LIB.SAVE.NAME_PLACEHOLDER')} />
                        </label>
                        <label className="flex flex-col gap-1 text-sm text-black-800">
                            {t('SECTIONS_LIB.SAVE.DESCRIPTION')}
                            <AppInput value={description} maxLength={500} onChange={(event: any) => setDescription(event.target.value)} />
                        </label>
                        <div className="flex justify-end gap-2">
                            <Button type="button" variant="secondary" className="min-h-11" onClick={() => close(false)}>
                                {t('SECTIONS_LIB.CANCEL')}
                            </Button>
                            <Button type="submit" className="min-h-11" disabled={!name.trim() || busy}>
                                {t('SECTIONS_LIB.SAVE.SUBMIT')}
                            </Button>
                        </div>
                    </form>
                )}
            </DialogContent>
        </Dialog>
    );
}
