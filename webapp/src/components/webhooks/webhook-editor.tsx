'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Field, inputClass } from '@app/components/registration/field';
import { Button } from '@app/shadcn/components/ui/button';
import { Switch } from '@app/shadcn/components/ui/switch';
import { WebhookDetail, WebhookVariable, WebhookWithSecret, useCreateWebhookMutation, useUpdateWebhookMutation } from '@app/store/workspaces/webhooks-api';
import { variableTypeKey } from '@app/utils/registration';
import { MAX_FIELDS, defaultKeyOf, errorCodeOf, errorField, errorKey, isValidKey, urlProblem } from '@app/utils/webhooks';

interface Props {
    workspaceId: string;
    formId: string;
    variables: WebhookVariable[];
    /** The webhook being edited; none creates one. */
    webhook?: WebhookDetail;
    onCreated: (created: WebhookWithSecret) => void;
    onSaved: () => void;
    onCancel: () => void;
}

/**
 * Adds or edits one webhook: the address (checked as it is typed, the server
 * has the last word), the questions that are sent and the name each gets.
 */
export default function WebhookEditor({ workspaceId, formId, variables, webhook, onCreated, onSaved, onCancel }: Props) {
    const { t } = useTranslation('builder');
    // the question types are named once, for the case-system screens too
    const typeLabel = (type: string) => {
        const key = variableTypeKey(type);
        return key ? t(key) : type.replace(/_/g, ' ');
    };
    const [create, { isLoading: creating }] = useCreateWebhookMutation();
    const [update, { isLoading: updating }] = useUpdateWebhookMutation();
    const [url, setUrl] = useState(webhook?.url ?? '');
    const [urlTouched, setUrlTouched] = useState(false);
    const [on, setOn] = useState(webhook?.enabled ?? true);
    // source -> the name it gets in the body
    const [chosen, setChosen] = useState<Record<string, string>>(() => Object.fromEntries((webhook?.fields ?? []).map((f) => [f.source, f.key])));
    const [serverErrors, setServerErrors] = useState<{ url?: string; fields?: string; general?: string }>({});
    const [keyErrors, setKeyErrors] = useState<Record<string, string>>({});
    const urlField = useRef<HTMLInputElement>(null);
    const heading = useRef<HTMLHeadingElement>(null);

    useEffect(() => {
        heading.current?.focus();
    }, []);

    const problem = urlProblem(url);
    const urlError = serverErrors.url ?? (urlTouched && problem ? t(problem === 'empty' ? 'WEBHOOKS.EDITOR.URL_EMPTY' : problem === 'not_https' ? 'WEBHOOKS.ERROR.not_https' : 'WEBHOOKS.ERROR.invalid_url') : null);
    const choosable = (v: WebhookVariable) => v.supported;
    const count = Object.keys(chosen).length;
    const saving = creating || updating;
    const names = useMemo(() => variables.filter(choosable), [variables]);

    const toggle = (source: string, checked: boolean) => {
        setServerErrors((e) => ({ ...e, fields: undefined }));
        setChosen((current) => {
            const next = { ...current };
            if (checked) next[source] = defaultKeyOf(source);
            else delete next[source];
            return next;
        });
    };

    const submit = async (event: React.FormEvent) => {
        event.preventDefault();
        setServerErrors({});
        setUrlTouched(true);
        const badKeys: Record<string, string> = {};
        const seen = new Set<string>();
        for (const [source, key] of Object.entries(chosen)) {
            const name = key.trim();
            if (!isValidKey(name)) badKeys[source] = t('WEBHOOKS.ERROR.invalid_key');
            else if (seen.has(name)) badKeys[source] = t('WEBHOOKS.EDITOR.KEY_TAKEN');
            seen.add(name);
        }
        setKeyErrors(badKeys);
        if (problem) {
            urlField.current?.focus();
            return;
        }
        if (Object.keys(badKeys).length > 0) return;
        if (count > MAX_FIELDS) {
            setServerErrors({ fields: t('WEBHOOKS.ERROR.too_many_fields') });
            return;
        }
        const fields = Object.entries(chosen).map(([source, key]) => ({ source, key: key.trim() }));
        const response: any = webhook ? await update({ workspaceId, formId, webhookId: webhook.id, body: { url: url.trim(), fields, enabled: on } }) : await create({ workspaceId, formId, body: { url: url.trim(), fields, enabled: on } });
        if (response.error) {
            const code = errorCodeOf(response.error);
            const message = t(errorKey(code));
            const field = errorField(code);
            if (field === 'url') {
                setServerErrors({ url: message });
                urlField.current?.focus();
            } else if (field === 'fields') setServerErrors({ fields: message });
            else setServerErrors({ general: message });
            return;
        }
        if (webhook) onSaved();
        else onCreated(response.data as WebhookWithSecret);
    };

    return (
        <form onSubmit={submit} noValidate className="flex flex-col gap-5 rounded-lg border border-black-300 bg-white p-4 md:p-5" aria-labelledby="webhook-editor-title" data-testid="webhook-editor">
            <h3 id="webhook-editor-title" ref={heading} tabIndex={-1} className="text-sm font-semibold text-black-900 outline-hidden">
                {t(webhook ? 'WEBHOOKS.EDITOR.TITLE_EDIT' : 'WEBHOOKS.EDITOR.TITLE_ADD')}
            </h3>

            <Field id="webhook-url" label={t('WEBHOOKS.EDITOR.URL')} hint={t('WEBHOOKS.EDITOR.URL_HINT')} error={urlError}>
                {(props) => (
                    <input
                        {...props}
                        ref={urlField}
                        type="url"
                        inputMode="url"
                        className={inputClass}
                        value={url}
                        maxLength={2048}
                        placeholder="https://"
                        autoComplete="off"
                        spellCheck={false}
                        onBlur={() => setUrlTouched(true)}
                        onChange={(e) => {
                            setServerErrors((current) => ({ ...current, url: undefined }));
                            setUrl(e.target.value);
                        }}
                    />
                )}
            </Field>

            <fieldset className="flex flex-col gap-2" aria-describedby={serverErrors.fields ? 'webhook-fields-error' : 'webhook-fields-hint'}>
                <legend className="text-sm font-medium text-black-900">{t('WEBHOOKS.EDITOR.FIELDS')}</legend>
                <p id="webhook-fields-hint" className="text-xs leading-relaxed text-black-600">
                    {t('WEBHOOKS.EDITOR.FIELDS_HINT')}
                </p>
                {names.length === 0 && <p className="text-sm text-black-700">{t('WEBHOOKS.EDITOR.NO_FIELDS')}</p>}
                <ul className="flex flex-col divide-y divide-black-200 rounded-md border border-black-300">
                    {variables.map((variable, index) => {
                        const key = chosen[variable.source];
                        const id = `webhook-var-${index}`;
                        const keyId = `${id}-key`;
                        const error = keyErrors[variable.source];
                        const can = choosable(variable);
                        return (
                            <li key={variable.source} className="flex flex-col gap-2 px-3 py-2.5" data-testid={`webhook-variable-${variable.source}`}>
                                <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
                                    <div className="flex min-w-0 items-start gap-2.5">
                                        <input
                                            id={id}
                                            type="checkbox"
                                            className="mt-0.5 h-4 w-4 shrink-0 accent-brand-500"
                                            checked={key !== undefined}
                                            disabled={!can}
                                            aria-describedby={!can ? `${id}-reason` : undefined}
                                            onChange={(e) => toggle(variable.source, e.target.checked)}
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
                                                <span id={`${id}-reason`}>{t(variable.reason === 'file_not_sent' ? 'WEBHOOKS.EDITOR.FILE_NOT_SENT' : 'WEBHOOKS.EDITOR.TYPE_NOT_SUPPORTED')}</span>
                                            </>
                                        )}
                                    </span>
                                </div>
                                {key !== undefined && (
                                    <div className="ml-6 flex flex-col gap-1">
                                        <label htmlFor={keyId} className="text-xs font-medium text-black-700">
                                            {t('WEBHOOKS.EDITOR.KEY')}
                                        </label>
                                        <input
                                            id={keyId}
                                            className={inputClass + ' sm:max-w-80'}
                                            value={key}
                                            maxLength={64}
                                            autoComplete="off"
                                            spellCheck={false}
                                            placeholder={defaultKeyOf(variable.source)}
                                            aria-invalid={!!error}
                                            aria-describedby={error ? `${keyId}-error` : undefined}
                                            onChange={(e) => {
                                                setKeyErrors((current) => ({ ...current, [variable.source]: '' }));
                                                setChosen((current) => ({ ...current, [variable.source]: e.target.value }));
                                            }}
                                        />
                                        {error && (
                                            <p id={`${keyId}-error`} className="text-xs font-medium text-[#A83434]">
                                                {error}
                                            </p>
                                        )}
                                    </div>
                                )}
                            </li>
                        );
                    })}
                </ul>
                {serverErrors.fields && (
                    <p id="webhook-fields-error" role="alert" className="text-xs font-medium text-[#A83434]">
                        {serverErrors.fields}
                    </p>
                )}
                <p className="text-xs text-black-600" aria-live="polite">
                    {t('WEBHOOKS.EDITOR.COUNT', { count })}
                </p>
            </fieldset>

            <div className="flex items-center gap-3">
                <Switch id="webhook-enabled" checked={on} aria-labelledby="webhook-enabled-label" onCheckedChange={setOn} />
                <label id="webhook-enabled-label" htmlFor="webhook-enabled" className="cursor-pointer text-sm font-medium text-black-900">
                    {t('WEBHOOKS.EDITOR.ENABLED')}
                </label>
            </div>
            <p className="max-w-[62ch] text-xs leading-relaxed text-black-600">{t('WEBHOOKS.EDITOR.ENABLED_HINT')}</p>

            {serverErrors.general && (
                <p role="alert" className="text-sm font-medium text-[#A83434]">
                    {serverErrors.general}
                </p>
            )}

            <div className="flex flex-wrap gap-3">
                <Button type="submit" size="sm" isLoading={saving} disabled={saving}>
                    {t(webhook ? 'WEBHOOKS.EDITOR.SAVE' : 'WEBHOOKS.EDITOR.ADD')}
                </Button>
                <Button type="button" variant="v2Button" size="sm" disabled={saving} onClick={onCancel}>
                    {t('WEBHOOKS.EDITOR.CANCEL')}
                </Button>
            </div>
        </form>
    );
}
