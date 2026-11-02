'use client';

import React, { useState } from 'react';

import { InternalFieldInput } from '@Components/form/internal-fields-panel';
import { Pencil } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { AnswerDto, StandardFormDto } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@app/shadcn/components/ui/dialog';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useEditResponseAnswersMutation } from '@app/store/workspaces/response-revisions-api';
import { InternalInputValue } from '@app/utils/internal-fields';
import { changedAnswers, editableQuestions, inputsFor, lockedQuestions, questionTitle } from '@app/utils/staff-answers';

/** The words for a refused edit: the server's code when it has one, else its own sentence, else a plain failure. */
function failureMessage(t: (key: string, options?: any) => string, error: any): string {
    const data = error?.data;
    const code = typeof data?.code === 'string' ? data.code : undefined;
    if (code) return t(`RESPONSE_EDIT.ERROR.${code}`, { defaultValue: typeof data?.message === 'string' ? data.message : t('RESPONSE_EDIT.ERROR.generic') });
    if (typeof data === 'string' && data.trim()) return data;
    if (typeof data?.message === 'string') return data.message;
    return t('RESPONSE_EDIT.ERROR.generic');
}

/**
 * "Edit answers" on a response (needs response.edit, behind the server's
 * RESPONSE_REVISIONS_ENABLED): the questions staff can change here, filled with
 * the stored answers; only what differs is sent, and the server checks it like
 * a respondent's own edit. Everything else the editor cannot change is listed.
 * The respondent is not told; the change is kept in the response's history.
 */
export default function EditAnswers({ workspaceId, formId, responseId, form, answers }: { workspaceId: string; formId: string; responseId: string; form: StandardFormDto; answers: Record<string, AnswerDto> }) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const [open, setOpen] = useState(false);
    const [values, setValues] = useState<Record<string, InternalInputValue>>({});
    const [failure, setFailure] = useState<string | null>(null);
    const [save, { isLoading }] = useEditResponseAnswersMutation();
    const fields = editableQuestions(form);
    const locked = lockedQuestions(form);
    const changes = changedAnswers(fields, answers, values);
    const changedCount = Object.keys(changes).length;

    // always from the stored answers as they are when it is opened
    const show = () => {
        setValues(inputsFor(fields, answers));
        setFailure(null);
        setOpen(true);
    };

    const submit = async () => {
        setFailure(null);
        const result: any = await save({ workspaceId, formId, responseId, answers: changes });
        if (result?.error) {
            setFailure(failureMessage(t, result.error));
            return;
        }
        setOpen(false);
        toast({ description: result?.data?.changed?.length ? t('RESPONSE_EDIT.SAVED', { count: result.data.changed.length }) : t('RESPONSE_EDIT.NOTHING_CHANGED') });
    };

    return (
        <>
            <Button variant="ghost" className="min-w-9 px-2!" title={t('RESPONSE_EDIT.BUTTON')} onClick={show} data-testid="edit-answers">
                <Pencil className="h-4 w-4 shrink-0 sm:mr-1.5" aria-hidden="true" />
                <span className="sr-only sm:not-sr-only">{t('RESPONSE_EDIT.BUTTON')}</span>
            </Button>
            <Dialog open={open} onOpenChange={(next) => !isLoading && setOpen(next)}>
                <DialogContent className="max-h-[90dvh] max-w-xl overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>{t('RESPONSE_EDIT.TITLE')}</DialogTitle>
                        <DialogDescription>{t('RESPONSE_EDIT.NOTE')}</DialogDescription>
                    </DialogHeader>
                    {fields.length === 0 ? (
                        <p className="text-sm">{t('RESPONSE_EDIT.NOTHING_TO_EDIT')}</p>
                    ) : (
                        <div className="flex flex-col gap-4">
                            {fields.map((field) => (
                                <div key={field.id} className="flex flex-col gap-1.5">
                                    <label id={`edit-label-${field.id}`} htmlFor={`internal-${field.id}`} className="text-sm leading-snug font-medium text-black-800">
                                        {questionTitle(field) || t('RESPONSE_EDIT.UNTITLED')}
                                        {field.validations?.required && <span className="ml-1 text-xs font-normal text-black-600">{t('RESPONSE_EDIT.REQUIRED')}</span>}
                                    </label>
                                    <InternalFieldInput field={field} labelledBy={`edit-label-${field.id}`} value={values[field.id]} onChange={(value) => setValues((previous) => ({ ...previous, [field.id]: value }))} />
                                </div>
                            ))}
                        </div>
                    )}
                    {locked.length > 0 && (
                        <p className="text-xs text-black-700" data-testid="locked-questions">
                            {t('RESPONSE_EDIT.LOCKED', { questions: locked.map((field) => questionTitle(field) || t('RESPONSE_EDIT.UNTITLED')).join(', ') })}
                        </p>
                    )}
                    <div role="alert" aria-live="assertive" className={failure ? 'text-danger-700 text-sm' : 'sr-only'}>
                        {failure}
                    </div>
                    <DialogFooter className="gap-2">
                        <Button variant="v2Button" onClick={() => setOpen(false)} disabled={isLoading}>
                            {t('RESPONSE_EDIT.CANCEL')}
                        </Button>
                        <Button variant="primary" onClick={submit} isLoading={isLoading} disabled={changedCount === 0 || isLoading}>
                            {t('RESPONSE_EDIT.SAVE', { count: changedCount })}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
