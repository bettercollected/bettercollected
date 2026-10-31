'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';

import { useTranslation } from 'react-i18next';

import ActionConditionEditor, { conditionIncomplete } from '@app/components/email-actions/action-condition-editor';
import { Field, inputClass } from '@app/components/registration/field';
import { Button } from '@app/shadcn/components/ui/button';
import { Switch } from '@app/shadcn/components/ui/switch';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { EmailAction, EmailVariable, useCreateEmailActionMutation, usePreviewEmailMutation, useUpdateEmailActionMutation } from '@app/store/workspaces/email-actions-api';
import type { ActionCondition } from '@app/store/workspaces/webhooks-api';
import { DEFAULT_TEMPLATES, EditorField, LANGUAGES, MAX_TEAM, NAME_MAX, TemplateLanguage, addressProblem, errorField, errorKey, insertPlaceholder, parseRecipients, placeholdersFor, templateProblem } from '@app/utils/email-actions';
import { variableTypeKey } from '@app/utils/registration';
import { defaultKeyOf, errorCodeOf, isValidKey } from '@app/utils/webhooks';

interface Props {
    workspaceId: string;
    formId: string;
    variables: EmailVariable[];
    /** The action being edited; none creates one. */
    action?: EmailAction;
    onSaved: () => void;
    onCancel: () => void;
}

function Err({ id, text }: { id: string; text?: string }) {
    return text ? (
        <p id={id} role="alert" className="text-xs font-medium text-[#A83434]">
            {text}
        </p>
    ) : null;
}

type Templates = Record<TemplateLanguage, { subject: string; body: string }>;

/**
 * Adds or edits one email action: who is mailed (the form's team, and/or a copy to
 * the signed-in respondent's verified account email), the words in English and
 * Dutch with a placeholder picker and a preview, the questions the words may
 * name, when it runs and whether it is on. The server has the last word.
 */
export default function EmailActionEditor({ workspaceId, formId, variables, action, onSaved, onCancel }: Props) {
    const { t } = useTranslation('builder');
    const typeLabel = (type: string) => {
        const key = variableTypeKey(type);
        return key ? t(key) : type.replace(/_/g, ' ');
    };
    // a copy goes only to an address its owner proved by signing in: the form asks for that when it requires a verified identity
    const asksForSignIn = !!useAppSelector(selectForm)?.settings?.requireVerifiedIdentity;
    const [create, { isLoading: creating }] = useCreateEmailActionMutation();
    const [update, { isLoading: updating }] = useUpdateEmailActionMutation();
    const [preview, { isLoading: previewing }] = usePreviewEmailMutation();
    const [name, setName] = useState(action?.name ?? '');
    const [team, setTeam] = useState((action?.teamRecipients ?? []).join('\n'));
    const [copy, setCopy] = useState(!!action?.respondentCopy);
    const [chosen, setChosen] = useState<Record<string, string>>(() => Object.fromEntries((action?.fields ?? []).map((f) => [f.source, f.key])));
    const [templates, setTemplates] = useState<Templates>({ en: action?.en ?? DEFAULT_TEMPLATES.en, nl: action?.nl ?? DEFAULT_TEMPLATES.nl });
    const [language, setLanguage] = useState<TemplateLanguage>('en');
    const [condition, setCondition] = useState<ActionCondition | null>(action?.condition ?? null);
    const [on, setOn] = useState(action?.enabled ?? true);
    const [shown, setShown] = useState<{ subject: string; body: string } | null>(null);
    const [errors, setErrors] = useState<Partial<Record<EditorField | 'general', string>>>({});
    const [keyErrors, setKeyErrors] = useState<Record<string, string>>({});
    const heading = useRef<HTMLHeadingElement>(null);
    const subjectField = useRef<HTMLInputElement>(null);
    const bodyField = useRef<HTMLTextAreaElement>(null);
    const lastFocused = useRef<'subject' | 'body'>('body');

    useEffect(() => {
        heading.current?.focus();
    }, []);

    const choosable = useMemo(() => variables.filter((v) => v.supported), [variables]);
    const keys = Object.values(chosen)
        .map((k) => k.trim())
        .filter(Boolean);
    const saving = creating || updating;
    const fail = (field: EditorField | 'general', message: string) => setErrors((e) => ({ ...e, [field]: message }));
    const clear = (field: EditorField) => setErrors((e) => ({ ...e, [field]: undefined }));
    const current = templates[language];

    const setTemplate = (part: 'subject' | 'body', value: string) => {
        clear('templates');
        setShown(null);
        setTemplates((all) => ({ ...all, [language]: { ...all[language], [part]: value } }));
    };

    const insert = (placeholder: string) => {
        const part = lastFocused.current;
        const field = part === 'subject' ? subjectField.current : bodyField.current;
        const text = current[part];
        const { text: next, cursor } = insertPlaceholder(text, placeholder, field?.selectionStart ?? text.length, field?.selectionEnd ?? text.length);
        setTemplate(part, next);
        requestAnimationFrame(() => {
            field?.focus();
            field?.setSelectionRange(cursor, cursor);
        });
    };

    const toggleQuestion = (source: string, checked: boolean) => {
        clear('fields');
        setShown(null);
        setChosen((c) => {
            const next = { ...c };
            if (checked) next[source] = defaultKeyOf(source);
            else delete next[source];
            return next;
        });
    };

    const showPreview = async () => {
        setShown(null);
        const response: any = await preview({ workspaceId, formId, body: { language, subject: current.subject, body: current.body, fields: Object.entries(chosen).map(([source, key]) => ({ source, key: key.trim() })) } });
        if (response.error) fail('templates', t(errorKey(errorCodeOf(response.error))));
        else {
            clear('templates');
            setShown(response.data);
        }
    };

    const submit = async (event: React.FormEvent) => {
        event.preventDefault();
        setErrors({});
        const problems: Partial<Record<EditorField, string>> = {};
        const badKeys: Record<string, string> = {};
        const seen = new Set<string>();
        for (const [source, key] of Object.entries(chosen)) {
            const value = key.trim();
            if (!isValidKey(value)) badKeys[source] = t('EMAIL_ACTIONS.ERROR.invalid_key');
            else if (seen.has(value)) badKeys[source] = t('EMAIL_ACTIONS.EDITOR.KEY_TAKEN');
            seen.add(value);
        }
        setKeyErrors(badKeys);
        if (!name.trim()) problems.name = t('EMAIL_ACTIONS.ERROR.invalid_name');
        const addresses = parseRecipients(team);
        if (addresses.length > MAX_TEAM) problems.recipients = t('EMAIL_ACTIONS.ERROR.too_many_recipients');
        else if (addresses.some(addressProblem)) problems.recipients = t('EMAIL_ACTIONS.ERROR.invalid_recipient');
        else if (addresses.length === 0 && !copy) problems.recipients = t('EMAIL_ACTIONS.ERROR.no_recipient');
        for (const lang of LANGUAGES) {
            const tpl = templates[lang];
            if (!tpl.subject.trim() || !tpl.body.trim()) problems.templates = t('EMAIL_ACTIONS.ERROR.template_missing');
            else {
                const bad = templateProblem(tpl.subject, placeholdersFor(keys, 'subject')) ?? templateProblem(tpl.body, placeholdersFor(keys, 'body'));
                if (bad) problems.templates = bad.code === 'unknown_placeholder' ? t('EMAIL_ACTIONS.EDITOR.UNKNOWN_PLACEHOLDER', { name: `{{${bad.name}}}` }) : t('EMAIL_ACTIONS.ERROR.invalid_placeholder');
            }
        }
        if (conditionIncomplete(condition)) problems.condition = t('ACTION_CONDITION.INCOMPLETE');
        if (Object.keys(problems).length > 0 || Object.keys(badKeys).length > 0) {
            setErrors(problems);
            return;
        }
        const body = {
            name: name.trim(),
            enabled: on,
            en: templates.en,
            nl: templates.nl,
            fields: Object.entries(chosen).map(([source, key]) => ({ source, key: key.trim() })),
            teamRecipients: addresses,
            respondentCopy: copy,
            condition
        };
        const response: any = action ? await update({ workspaceId, formId, actionId: action.id, body }) : await create({ workspaceId, formId, body });
        if (response.error) {
            const code = errorCodeOf(response.error);
            fail(errorField(code) ?? 'general', t(errorKey(code)));
            return;
        }
        onSaved();
    };

    return (
        <form onSubmit={submit} noValidate className="flex flex-col gap-6 rounded-lg border border-black-300 bg-white p-4 md:p-5" aria-labelledby="email-editor-title" data-testid="email-editor">
            <h3 id="email-editor-title" ref={heading} tabIndex={-1} className="text-sm font-semibold text-black-900 outline-hidden">
                {t(action ? 'EMAIL_ACTIONS.EDITOR.TITLE_EDIT' : 'EMAIL_ACTIONS.EDITOR.TITLE_ADD')}
            </h3>

            <Field id="email-name" label={t('EMAIL_ACTIONS.EDITOR.NAME')} error={errors.name}>
                {(props) => <input {...props} className={inputClass} value={name} maxLength={NAME_MAX} autoComplete="off" onChange={(e) => (clear('name'), setName(e.target.value))} />}
            </Field>

            <fieldset className="flex flex-col gap-4" aria-describedby="email-recipients-hint">
                <legend className="text-sm font-medium text-black-900">{t('EMAIL_ACTIONS.EDITOR.RECIPIENTS')}</legend>
                <p id="email-recipients-hint" className="max-w-[62ch] text-xs leading-relaxed text-black-600">
                    {t('EMAIL_ACTIONS.EDITOR.RECIPIENTS_HINT')}
                </p>
                <Field id="email-team" label={t('EMAIL_ACTIONS.EDITOR.TEAM')} hint={t('EMAIL_ACTIONS.EDITOR.TEAM_HINT', { count: MAX_TEAM })} error={errors.recipients}>
                    {(props) => <textarea {...props} className={inputClass + ' h-24 py-2'} value={team} spellCheck={false} autoComplete="off" onChange={(e) => (clear('recipients'), setTeam(e.target.value))} />}
                </Field>
                <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-3">
                        <Switch id="email-copy" checked={copy} aria-labelledby="email-copy-label" onCheckedChange={(v) => (clear('recipients'), setCopy(v))} />
                        <label id="email-copy-label" htmlFor="email-copy" className="cursor-pointer text-sm font-medium text-black-900">
                            {t('EMAIL_ACTIONS.EDITOR.COPY')}
                        </label>
                    </div>
                    <p className="max-w-[62ch] text-xs leading-relaxed text-black-600">{t('EMAIL_ACTIONS.EDITOR.COPY_HINT')}</p>
                    {copy && (
                        <p role={asksForSignIn ? undefined : 'alert'} data-testid="email-copy-verification" className={asksForSignIn ? 'max-w-[62ch] text-xs leading-relaxed text-black-700' : 'max-w-[62ch] rounded-md border border-[#E5B9B9] bg-[#FBEFEF] px-3 py-2 text-xs leading-relaxed font-medium text-[#8A2B2B]'}>
                            {t(asksForSignIn ? 'EMAIL_ACTIONS.EDITOR.COPY_VERIFIED' : 'EMAIL_ACTIONS.EDITOR.COPY_UNVERIFIED')}
                        </p>
                    )}
                </div>
            </fieldset>

            <fieldset className="flex flex-col gap-2" aria-describedby="email-fields-hint">
                <legend className="text-sm font-medium text-black-900">{t('EMAIL_ACTIONS.EDITOR.FIELDS')}</legend>
                <p id="email-fields-hint" className="max-w-[62ch] text-xs leading-relaxed text-black-600">
                    {t('EMAIL_ACTIONS.EDITOR.FIELDS_HINT', { name: '{{name}}' })}
                </p>
                {choosable.length === 0 && <p className="text-sm text-black-700">{t('EMAIL_ACTIONS.EDITOR.NO_FIELDS')}</p>}
                <ul className="flex flex-col divide-y divide-black-200 rounded-md border border-black-300">
                    {variables.map((variable, index) => {
                        const key = chosen[variable.source];
                        const id = `email-var-${index}`;
                        const can = variable.supported;
                        return (
                            <li key={variable.source} className="flex flex-col gap-2 px-3 py-2.5" data-testid={`email-variable-${variable.source}`}>
                                <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
                                    <div className="flex min-w-0 items-start gap-2.5">
                                        <input
                                            id={id}
                                            type="checkbox"
                                            className="mt-0.5 h-4 w-4 shrink-0 accent-brand-500"
                                            checked={key !== undefined}
                                            disabled={!can}
                                            aria-describedby={!can ? `${id}-reason` : undefined}
                                            onChange={(e) => toggleQuestion(variable.source, e.target.checked)}
                                        />
                                        <label htmlFor={id} className={can ? 'text-sm break-words text-black-900' : 'text-sm break-words text-black-600'}>
                                            {variable.label}
                                        </label>
                                    </div>
                                    <span className="text-xs text-black-600">
                                        {typeLabel(variable.type)}
                                        {!can && (
                                            <>
                                                {' · '}
                                                <span id={`${id}-reason`}>{t(variable.reason === 'file_not_sent' ? 'EMAIL_ACTIONS.EDITOR.FILE_NOT_SENT' : 'EMAIL_ACTIONS.EDITOR.TYPE_NOT_SUPPORTED')}</span>
                                            </>
                                        )}
                                    </span>
                                </div>
                                {key !== undefined && (
                                    <div className="ml-6 flex flex-col gap-1">
                                        <label htmlFor={`${id}-key`} className="text-xs font-medium text-black-700">
                                            {t('EMAIL_ACTIONS.EDITOR.KEY')}
                                        </label>
                                        <input
                                            id={`${id}-key`}
                                            className={inputClass + ' sm:max-w-80'}
                                            value={key}
                                            maxLength={64}
                                            autoComplete="off"
                                            spellCheck={false}
                                            aria-invalid={!!keyErrors[variable.source]}
                                            onChange={(e) => (setKeyErrors((k) => ({ ...k, [variable.source]: '' })), setShown(null), setChosen((c) => ({ ...c, [variable.source]: e.target.value })))}
                                        />
                                        <Err id={`${id}-key-error`} text={keyErrors[variable.source]} />
                                    </div>
                                )}
                            </li>
                        );
                    })}
                </ul>
                <Err id="email-fields-error" text={errors.fields} />
            </fieldset>

            <fieldset className="flex flex-col gap-3" aria-describedby="email-templates-hint">
                <legend className="text-sm font-medium text-black-900">{t('EMAIL_ACTIONS.EDITOR.TEMPLATES')}</legend>
                <p id="email-templates-hint" className="max-w-[62ch] text-xs leading-relaxed text-black-600">
                    {t('EMAIL_ACTIONS.EDITOR.TEMPLATES_HINT')}
                </p>
                <div role="radiogroup" aria-label={t('EMAIL_ACTIONS.EDITOR.LANGUAGE')} className="flex gap-2">
                    {LANGUAGES.map((lang) => (
                        <label key={lang} className={'cursor-pointer rounded-md border px-3 py-1.5 text-sm ' + (language === lang ? 'border-brand-500 bg-brand-100 text-black-900' : 'border-black-300 text-black-800')}>
                            <input type="radio" name="email-language" className="sr-only" checked={language === lang} onChange={() => (setLanguage(lang), setShown(null))} />
                            {t(`EMAIL_ACTIONS.EDITOR.LANGUAGE_${lang.toUpperCase()}`)}
                        </label>
                    ))}
                </div>
                <Field id="email-subject" label={t('EMAIL_ACTIONS.EDITOR.SUBJECT')}>
                    {(props) => (
                        <input {...props} ref={subjectField} className={inputClass} value={current.subject} maxLength={200} autoComplete="off" onFocus={() => (lastFocused.current = 'subject')} onChange={(e) => setTemplate('subject', e.target.value)} />
                    )}
                </Field>
                <Field id="email-body" label={t('EMAIL_ACTIONS.EDITOR.BODY')} error={errors.templates}>
                    {(props) => (
                        <textarea {...props} ref={bodyField} className={inputClass + ' h-44 py-2 font-mono'} value={current.body} maxLength={10000} onFocus={() => (lastFocused.current = 'body')} onChange={(e) => setTemplate('body', e.target.value)} />
                    )}
                </Field>
                <div className="flex flex-col gap-1.5">
                    <span id="email-placeholders-label" className="text-xs font-medium text-black-700">
                        {t('EMAIL_ACTIONS.EDITOR.PLACEHOLDERS')}
                    </span>
                    <div role="group" aria-labelledby="email-placeholders-label" className="flex flex-wrap gap-1.5">
                        {placeholdersFor(keys, 'body').map((placeholder) => (
                            <button
                                key={placeholder}
                                type="button"
                                className="rounded-md border border-black-300 bg-black-100 px-2 py-1 font-mono text-xs text-black-800 hover:border-brand-500"
                                onClick={() => insert(placeholder)}
                                aria-label={t('EMAIL_ACTIONS.EDITOR.INSERT', { name: placeholder })}
                            >
                                {`{{${placeholder}}}`}
                            </button>
                        ))}
                    </div>
                    <p className="text-xs text-black-600">{t('EMAIL_ACTIONS.EDITOR.PLAIN_TEXT', { answers: '{{answers}}' })}</p>
                </div>
                <div className="flex flex-col gap-2">
                    <div>
                        <Button type="button" variant="v2Button" size="sm" isLoading={previewing} disabled={previewing} onClick={showPreview}>
                            {t('EMAIL_ACTIONS.EDITOR.PREVIEW')}
                        </Button>
                    </div>
                    <div aria-live="polite" data-testid="email-preview">
                        {shown && (
                            <div className="flex flex-col gap-2 rounded-md border border-black-300 bg-black-100 p-3">
                                <p className="text-xs font-medium text-black-600">{t('EMAIL_ACTIONS.EDITOR.PREVIEW_NOTE')}</p>
                                <p className="text-sm font-semibold break-words text-black-900">{shown.subject}</p>
                                <pre className="font-sans text-sm leading-relaxed break-words whitespace-pre-wrap text-black-800">{shown.body}</pre>
                            </div>
                        )}
                    </div>
                </div>
            </fieldset>

            <ActionConditionEditor
                idPrefix="email"
                value={condition}
                error={errors.condition}
                onChange={(next) => {
                    clear('condition');
                    setCondition(next);
                }}
            />

            <div className="flex items-center gap-3">
                <Switch id="email-enabled" checked={on} aria-labelledby="email-enabled-label" onCheckedChange={setOn} />
                <label id="email-enabled-label" htmlFor="email-enabled" className="cursor-pointer text-sm font-medium text-black-900">
                    {t('EMAIL_ACTIONS.EDITOR.ENABLED')}
                </label>
            </div>
            <p className="max-w-[62ch] text-xs leading-relaxed text-black-600">{t('EMAIL_ACTIONS.EDITOR.ENABLED_HINT')}</p>

            <Err id="email-general-error" text={errors.general} />

            <div className="flex flex-wrap gap-3">
                <Button type="submit" size="sm" isLoading={saving} disabled={saving}>
                    {t(action ? 'EMAIL_ACTIONS.EDITOR.SAVE' : 'EMAIL_ACTIONS.EDITOR.ADD')}
                </Button>
                <Button type="button" variant="v2Button" size="sm" disabled={saving} onClick={onCancel}>
                    {t('EMAIL_ACTIONS.EDITOR.CANCEL')}
                </Button>
            </div>
        </form>
    );
}
