'use client';

import { FormEvent, useEffect, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@app/shadcn/components/ui/dialog';
import { useUpdateAPIKeyMutation } from '@app/store/workspaces/api';

import { APIKey, keyFormScopeOf, keyStoredRoleOf } from './api-key';
import { keyErrorText } from './key-errors';
import KeyLimitsFields, { ScopeProblems, scopeLabelKey } from './key-limits-fields';
import { KeyFormScope, KeyLimits, KeyRole, StoredRole, UNKNOWN_ROLE, scopeProblems, submissionFormsOutsideList, widensKey } from './key-rules';

interface Draft {
    name: string;
    role: StoredRole;
    formScope: KeyFormScope;
    formIds: string[];
}

const draftOf = (key: APIKey): Draft => ({ name: key.name, role: keyStoredRoleOf(key), formScope: keyFormScopeOf(key), formIds: (key.forms ?? []).map((form) => form.id) });

const sameSet = (a: string[], b: string[]) => a.length === b.length && a.every((id) => b.includes(id));

/**
 * Edit a key: its name, role and forms, nothing else (what a key does is fixed at creation: that is a new key, with
 * a new secret). A change that gives the key more reach (a higher role, "every form" in place of a list, more forms)
 * shows a warning first and its button says what it does. A 409 `key_changed` (somebody else edited the key
 * meanwhile) offers to reload the key and try again; every other refusal is said in words and keeps the dialog open.
 */
export default function EditKeyDialog({
    keyItem,
    workspaceId,
    onClose,
    onReload,
    onSaved
}: {
    keyItem: APIKey | null;
    workspaceId: string;
    onClose: () => void;
    /** Reads the keys again and gives the one being edited as it is now (none: it is gone). */
    onReload: () => Promise<APIKey | undefined>;
    onSaved: (name: string) => void;
}) {
    const { t } = useTranslation();
    const [updateKey, { isLoading }] = useUpdateAPIKeyMutation();
    const [original, setOriginal] = useState<APIKey | null>(keyItem);
    const [draft, setDraft] = useState<Draft | null>(keyItem ? draftOf(keyItem) : null);
    const [error, setError] = useState<{ text: string; changed: boolean } | null>(null);

    // opening the dialog on another key starts from that key
    useEffect(() => {
        setOriginal(keyItem);
        setDraft(keyItem ? draftOf(keyItem) : null);
        setError(null);
    }, [keyItem?.id]);

    if (!keyItem || !original || !draft) return null;
    const before: KeyLimits = { role: keyStoredRoleOf(original), formScope: keyFormScopeOf(original), formIds: (original.forms ?? []).map((form) => form.id) };
    const after: KeyLimits = { role: draft.role, formScope: draft.formScope, formIds: draft.formScope === 'listed' ? draft.formIds : [] };
    const listed = draft.formScope === 'listed';
    const roleChanged = after.role !== before.role;
    const scopeChanged = after.formScope !== before.formScope || (listed && !sameSet(after.formIds, before.formIds));
    const nameChanged = draft.name.trim() !== original.name;
    const changed = roleChanged || scopeChanged || nameChanged;
    const widens = widensKey(before, after, original.scopes);
    // a stored role these screens do not know allows nothing on the server: it has to be replaced before anything else is saved
    const unknownRole = draft.role === UNKNOWN_ROLE;
    const problems = unknownRole ? [] : scopeProblems(draft.role as KeyRole | null, draft.formScope, original.scopes);
    const outside = submissionFormsOutsideList(original.submissionFormIds, draft.formScope, draft.formIds);
    // a list with nothing on it waits for a form, but only when the list itself is being changed: a key whose forms are all gone can still be renamed
    const listChanged = listed && (before.formScope !== 'listed' || !sameSet(after.formIds, before.formIds));
    const noForms = listChanged && draft.formIds.length === 0;
    const blocked = !draft.name.trim() || problems.length > 0 || outside.length > 0 || noForms || unknownRole;

    const patch = <K extends keyof Draft>(field: K, value: Draft[K]) => {
        setDraft((current) => (current ? { ...current, [field]: value } : current));
        setError(null);
    };

    const save = async (event: FormEvent) => {
        event.preventDefault();
        if (!changed || blocked || isLoading) return;
        // only what changed: a field left out stays as it is on the server
        const body: Record<string, unknown> = {};
        if (nameChanged) body.name = draft.name.trim();
        if (roleChanged) body.role = draft.role;
        if (scopeChanged) {
            body.formScope = draft.formScope;
            if (listed) body.formIds = draft.formIds;
        }
        const response: any = await updateKey({ workspace_id: workspaceId, key_id: original.id, body });
        if (response.data) {
            onSaved(draft.name.trim());
            onClose();
            return;
        }
        const code = response.error?.data?.code;
        // a list that holds forms the editor cannot open is refused whole: say which forms those are
        const unopenable = (original.forms ?? []).filter((form) => !form.title && draft.formIds.includes(form.id)).length;
        const text = code === 'form_not_in_workspace' && unopenable > 0 ? t('STAFF.API_KEYS.ERR_FORM_UNOPENABLE', { count: unopenable }) : keyErrorText(t, response.error, 'STAFF.API_KEYS.SAVE_FAILED');
        setError({ text, changed: code === 'key_changed' });
    };

    const reload = async () => {
        const fresh = await onReload();
        if (!fresh) {
            onClose();
            return;
        }
        setOriginal(fresh);
        setDraft(draftOf(fresh));
        setError(null);
    };

    return (
        <Dialog open onOpenChange={(open: boolean) => !open && onClose()}>
            <DialogContent title={t('STAFF.API_KEYS.EDIT_TITLE', { name: original.name })} className="max-h-[calc(100dvh-2rem)] max-w-xl overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>{t('STAFF.API_KEYS.EDIT_TITLE', { name: original.name })}</DialogTitle>
                    <DialogDescription>{t('STAFF.API_KEYS.EDIT_HINT')}</DialogDescription>
                </DialogHeader>
                <form className="flex flex-col gap-4" onSubmit={save} noValidate>
                    <div className="flex flex-col gap-1.5">
                        <label htmlFor="edit-key-name" className="text-[13px] font-semibold text-black-900">
                            {t('STAFF.API_KEYS.NAME_LABEL')}
                        </label>
                        <input
                            id="edit-key-name"
                            value={draft.name}
                            maxLength={60}
                            onChange={(event) => patch('name', event.target.value)}
                            className="border-control h-11 w-full rounded-md border bg-white px-3.5 text-sm text-black-900 outline-hidden transition duration-150 focus:border-brand-500 sm:h-10"
                        />
                    </div>
                    <div className="flex flex-col gap-1.5">
                        <p className="text-[13px] font-semibold text-black-900">{t('STAFF.API_KEYS.SCOPES_LABEL')}</p>
                        <ul className="flex flex-wrap gap-1.5">
                            {original.scopes.map((scope) => (
                                <li key={scope} className="rounded bg-black-100 px-1.5 py-0.5 text-[10.5px] text-black-600">
                                    {t(scopeLabelKey(scope))}
                                </li>
                            ))}
                        </ul>
                    </div>
                    <KeyLimitsFields
                        idPrefix="edit-key"
                        scopes={original.scopes}
                        role={draft.role}
                        unknownRole={original.role}
                        onRoleChange={(role) => patch('role', role)}
                        formScope={draft.formScope}
                        onFormScopeChange={(formScope) => patch('formScope', formScope)}
                        formIds={draft.formIds}
                        onFormIdsChange={(ids) => patch('formIds', ids)}
                        knownForms={original.forms}
                        hideScopeProblems
                    />
                    <ScopeProblems role={unknownRole ? null : (draft.role as KeyRole | null)} formScope={draft.formScope} scopes={original.scopes} />
                    {outside.length > 0 && (
                        <p role="alert" className="rounded-md border border-[#E8C4C4] bg-[#FBEFEF] p-3 text-xs text-[#8F2C2C]">
                            {t('STAFF.API_KEYS.ERR_SUBMISSION_OUTSIDE')}
                        </p>
                    )}
                    {noForms && <p className="text-xs text-black-700">{t('STAFF.API_KEYS.PICK_A_FORM')}</p>}
                    {unknownRole && (
                        <div role="alert" className="flex flex-col gap-1 rounded-md border border-[#F0D9B5] bg-[#FDF8EF] p-3">
                            <p className="text-xs leading-relaxed text-black-800">{t('STAFF.API_KEYS.UNKNOWN_ROLE_WARNING', { role: original.role })}</p>
                        </div>
                    )}
                    {widens && (
                        <div role="alert" className="flex flex-col gap-1 rounded-md border border-[#F0D9B5] bg-[#FDF8EF] p-3">
                            <p className="text-xs leading-relaxed text-black-800">{t('STAFF.API_KEYS.WIDEN_WARNING')}</p>
                        </div>
                    )}
                    {error && (
                        <div role="alert" className="flex flex-col gap-2 rounded-md border border-[#E8C4C4] bg-[#FBEFEF] p-3 text-xs text-[#8F2C2C]">
                            <p>{error.text}</p>
                            {error.changed && (
                                <div>
                                    <Button type="button" size="sm" variant="v2Button" className="min-h-11" onClick={reload}>
                                        {t('STAFF.API_KEYS.RELOAD')}
                                    </Button>
                                </div>
                            )}
                        </div>
                    )}
                    <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                        <Button type="button" variant="v2Button" className="min-h-11" onClick={onClose}>
                            {t('STAFF.API_KEYS.CANCEL')}
                        </Button>
                        <Button type="submit" variant={widens ? 'danger' : 'primary'} className="min-h-11" isLoading={isLoading} disabled={!changed || blocked}>
                            {widens ? t('STAFF.API_KEYS.WIDEN_CONFIRM') : t('STAFF.API_KEYS.SAVE')}
                        </Button>
                    </div>
                </form>
            </DialogContent>
        </Dialog>
    );
}
