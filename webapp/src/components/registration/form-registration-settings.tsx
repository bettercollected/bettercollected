'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';

import Link from 'next/link';

import { useTranslation } from 'react-i18next';

import { Field, inputClass } from '@app/components/registration/field';
import { useRegistrationEnabled } from '@app/components/registration/use-registration-enabled';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button } from '@app/shadcn/components/ui/button';
import { Switch } from '@app/shadcn/components/ui/switch';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetFormRegistrationQuery, useGetRegistrationServicesQuery, useGetRegistrationVariablesQuery, useSaveFormRegistrationMutation } from '@app/store/workspaces/registration-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { canBeList, defaultKeyOf, errorCodeOf, errorKey, formErrorField, isValidKey, variableReasonKey } from '@app/utils/registration';

interface Chosen {
    key: string;
    asList: boolean;
}

/**
 * The Settings tab's "Send submissions to a case system": shown to owners and
 * admins (workspace.manage), while this server has the feature on, for forms
 * built here (an imported form is not collected here).
 */
export default function FormRegistrationSection() {
    const { enabled } = useRegistrationEnabled();
    const { can } = useWorkspacePermissions();
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const provider = form?.settings?.provider;
    if (!enabled || !can(WorkspacePermission.WORKSPACE_MANAGE) || !workspace?.id || !form?.formId || (provider && provider !== 'self')) return null;
    return <FormRegistrationSettings workspaceId={workspace.id} workspaceName={workspace.workspaceName} formId={form.formId} />;
}

export function FormRegistrationSettings({ workspaceId, workspaceName, formId }: { workspaceId: string; workspaceName?: string; formId: string }) {
    const { t } = useTranslation('builder');
    const registrationQuery = useGetFormRegistrationQuery({ workspaceId, formId });
    const servicesQuery = useGetRegistrationServicesQuery(workspaceId);
    const variablesQuery = useGetRegistrationVariablesQuery({ workspaceId, formId });
    const [save, { isLoading: saving }] = useSaveFormRegistrationMutation();

    const [on, setOn] = useState(false);
    const [serviceId, setServiceId] = useState('');
    const [path, setPath] = useState('');
    const [chosen, setChosen] = useState<Record<string, Chosen>>({});
    const [dropped, setDropped] = useState(0);
    const [errors, setErrors] = useState<{ service?: string; path?: string; variables?: string }>({});
    const [keyErrors, setKeyErrors] = useState<Record<string, string>>({});
    const [general, setGeneral] = useState<string | null>(null);
    const [saved, setSaved] = useState(false);
    const initialisedFor = useRef<string | null>(null);

    const variables = variablesQuery.data;
    const registration = registrationQuery.data;

    // Fill the draft once per form, when both answers are in; later refetches
    // (focus, after a save) must not wipe what is being edited.
    useEffect(() => {
        if (!registration || !variables || initialisedFor.current === formId) return;
        initialisedFor.current = formId;
        const known = new Set(variables.filter((v) => v.supported).map((v) => v.source));
        const list = new Set(registration.transformToList);
        const next: Record<string, Chosen> = {};
        let missing = 0;
        registration.variables.forEach((mapping) => {
            if (!known.has(mapping.source)) {
                missing += 1;
                return;
            }
            next[mapping.source] = { key: mapping.key ?? '', asList: list.has(mapping.source) };
        });
        setOn(registration.enabled);
        setServiceId(registration.serviceId ?? '');
        setPath(registration.path ?? '');
        setChosen(next);
        setDropped(missing);
    }, [registration, variables, formId]);

    const services = servicesQuery.data ?? [];
    const loading = registrationQuery.isLoading || variablesQuery.isLoading || servicesQuery.isLoading;
    const loadFailed = registrationQuery.isError || variablesQuery.isError;
    const selectedService = useMemo(() => services.find((s) => s.id === serviceId), [services, serviceId]);

    const touch = () => setSaved(false);

    const toggleVariable = (source: string, checked: boolean) => {
        touch();
        setChosen((current) => {
            const next = { ...current };
            if (checked) next[source] = { key: '', asList: false };
            else delete next[source];
            return next;
        });
    };

    const submit = async (event: React.FormEvent) => {
        event.preventDefault();
        setSaved(false);
        setGeneral(null);
        const sources = (variables ?? []).filter((v) => chosen[v.source]).map((v) => v.source);
        const found: typeof errors = {};
        const keyProblems: Record<string, string> = {};
        if (on) {
            if (!serviceId) found.service = t('REGISTRATION.ERROR.service_required');
            if (sources.length === 0) found.variables = t('REGISTRATION.ERROR.variables_required');
            const seen = new Set<string>();
            sources.forEach((source) => {
                const key = chosen[source].key.trim() || defaultKeyOf(source);
                if (!isValidKey(key)) keyProblems[source] = t('REGISTRATION.ERROR.invalid_key');
                else if (seen.has(key)) keyProblems[source] = t('REGISTRATION.FORM.KEY_TAKEN');
                seen.add(key);
            });
        }
        setErrors(found);
        setKeyErrors(keyProblems);
        if (Object.keys(found).length || Object.keys(keyProblems).length) return;

        const response: any = await save({
            workspaceId,
            formId,
            body: {
                enabled: on,
                serviceId: serviceId || null,
                path: path.trim(),
                variables: sources.map((source) => ({ source, key: chosen[source].key.trim() || undefined })),
                transformToList: sources.filter((source) => chosen[source].asList && canBeList(variables!.find((v) => v.source === source)!))
            }
        });
        if (response.data) {
            setSaved(true);
            setDropped(0);
            return;
        }
        const code = errorCodeOf(response.error);
        const sentence = t(errorKey(code));
        const field = formErrorField(code);
        if (field) setErrors({ [field]: sentence });
        else setGeneral(sentence);
    };

    return (
        <section className="flex flex-col gap-3" aria-labelledby="registration-form-title" data-testid="registration-form-settings">
            <h2 id="registration-form-title" className="text-xs font-semibold tracking-wide text-black-600 uppercase">
                {t('REGISTRATION.FORM.TITLE')}
            </h2>
            <p className="max-w-[62ch] text-sm leading-relaxed text-black-700">{t('REGISTRATION.FORM.INTRO')}</p>
            <p className="max-w-[62ch] rounded-md border border-black-300 bg-black-100 px-3 py-2 text-xs leading-relaxed text-black-700">{t('REGISTRATION.NOTICE')}</p>

            {loading && <p className="text-sm text-black-600">{t('REGISTRATION.LOADING')}</p>}
            {loadFailed && (
                <p role="alert" className="text-sm text-[#A83434]">
                    {t('REGISTRATION.FORM.LOAD_ERROR')}
                </p>
            )}

            {!loading && !loadFailed && registration && variables && (
                <form onSubmit={submit} noValidate className="flex flex-col gap-5">
                    <div className="flex items-center gap-3">
                        <Switch
                            id="registration-enabled"
                            checked={on}
                            aria-labelledby="registration-enabled-label"
                            onCheckedChange={(checked) => {
                                touch();
                                setOn(checked);
                            }}
                        />
                        <label id="registration-enabled-label" htmlFor="registration-enabled" className="cursor-pointer text-sm font-medium text-black-900">
                            {t('REGISTRATION.FORM.ENABLE')}
                        </label>
                    </div>

                    {on && (
                        <>
                            <Field
                                id="registration-form-service"
                                label={t('REGISTRATION.FORM.SERVICE')}
                                error={errors.service}
                                hint={
                                    services.length === 0 ? (
                                        <>
                                            {t('REGISTRATION.FORM.NO_SERVICES')}{' '}
                                            <Link href={`/${workspaceName}/dashboard/case-system`} className="font-medium text-brand-600 underline">
                                                {t('REGISTRATION.FORM.ADD_SERVICE')}
                                            </Link>
                                        </>
                                    ) : undefined
                                }
                            >
                                {(props) => (
                                    <select
                                        {...props}
                                        className={inputClass}
                                        value={serviceId}
                                        onChange={(e) => {
                                            touch();
                                            setServiceId(e.target.value);
                                        }}
                                    >
                                        <option value="">{t('REGISTRATION.FORM.SERVICE_PLACEHOLDER')}</option>
                                        {services.map((service) => (
                                            <option key={service.id} value={service.id}>
                                                {service.name}
                                            </option>
                                        ))}
                                    </select>
                                )}
                            </Field>
                            {selectedService && <p className="-mt-3 text-xs text-black-600">{t('REGISTRATION.FORM.SENDS_TO', { address: selectedService.baseUrl })}</p>}

                            <Field id="registration-form-path" label={t('REGISTRATION.FORM.PATH')} hint={t('REGISTRATION.FORM.PATH_HINT')} error={errors.path}>
                                {(props) => (
                                    <input
                                        {...props}
                                        className={inputClass}
                                        value={path}
                                        maxLength={255}
                                        placeholder="/cases"
                                        autoComplete="off"
                                        spellCheck={false}
                                        onChange={(e) => {
                                            touch();
                                            setPath(e.target.value);
                                        }}
                                    />
                                )}
                            </Field>

                            <fieldset className="flex flex-col gap-2" aria-describedby={errors.variables ? 'registration-variables-error' : 'registration-variables-hint'}>
                                <legend className="text-sm font-medium text-black-900">{t('REGISTRATION.FORM.VARIABLES')}</legend>
                                <p id="registration-variables-hint" className="text-xs leading-relaxed text-black-600">
                                    {t('REGISTRATION.FORM.VARIABLES_HINT')}
                                </p>
                                {dropped > 0 && (
                                    <p role="status" className="text-xs text-black-700">
                                        {t('REGISTRATION.FORM.DROPPED', { count: dropped })}
                                    </p>
                                )}
                                {variables.length === 0 && <p className="text-sm text-black-700">{t('REGISTRATION.FORM.NO_VARIABLES')}</p>}
                                <ul className="flex flex-col divide-y divide-black-200 rounded-md border border-black-300">
                                    {variables.map((variable, index) => {
                                        const row = chosen[variable.source];
                                        // by position: a source can hold characters an id cannot
                                        const checkboxId = `registration-var-${index}`;
                                        const keyId = `${checkboxId}-key`;
                                        const keyError = keyErrors[variable.source];
                                        return (
                                            <li key={variable.source} className="flex flex-col gap-2 px-3 py-2.5" data-testid={`registration-variable-${variable.source}`}>
                                                <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
                                                    <div className="flex min-w-0 items-start gap-2.5">
                                                        <input
                                                            id={checkboxId}
                                                            type="checkbox"
                                                            className="mt-0.5 h-4 w-4 shrink-0 accent-brand-500"
                                                            checked={!!row}
                                                            disabled={!variable.supported}
                                                            aria-describedby={!variable.supported ? `${checkboxId}-reason` : undefined}
                                                            onChange={(e) => toggleVariable(variable.source, e.target.checked)}
                                                        />
                                                        <label htmlFor={checkboxId} className={variable.supported ? 'text-sm break-words text-black-900' : 'text-sm break-words text-black-600'}>
                                                            {variable.label}
                                                        </label>
                                                    </div>
                                                    <span className="text-xs text-black-600">
                                                        {variable.type.replace(/_/g, ' ')}
                                                        {!variable.supported && (
                                                            <>
                                                                {' · '}
                                                                <span id={`${checkboxId}-reason`}>{t(variableReasonKey(variable.reason))}</span>
                                                            </>
                                                        )}
                                                    </span>
                                                </div>
                                                {row && (
                                                    <div className="ml-6 flex flex-col gap-2 sm:flex-row sm:items-start">
                                                        <div className="flex flex-1 flex-col gap-1">
                                                            <label htmlFor={keyId} className="text-xs font-medium text-black-700">
                                                                {t('REGISTRATION.FORM.KEY')}
                                                            </label>
                                                            <input
                                                                id={keyId}
                                                                className={inputClass}
                                                                value={row.key}
                                                                maxLength={64}
                                                                autoComplete="off"
                                                                spellCheck={false}
                                                                placeholder={defaultKeyOf(variable.source)}
                                                                aria-invalid={!!keyError}
                                                                aria-describedby={keyError ? `${keyId}-error` : undefined}
                                                                onChange={(e) => {
                                                                    touch();
                                                                    setChosen((current) => ({ ...current, [variable.source]: { ...current[variable.source], key: e.target.value } }));
                                                                }}
                                                            />
                                                            {keyError && (
                                                                <p id={`${keyId}-error`} className="text-xs font-medium text-[#A83434]">
                                                                    {keyError}
                                                                </p>
                                                            )}
                                                        </div>
                                                        {canBeList(variable) && (
                                                            <label className="flex items-center gap-2 pt-1 text-sm text-black-800 sm:mt-6">
                                                                <input
                                                                    type="checkbox"
                                                                    className="h-4 w-4 accent-brand-500"
                                                                    checked={row.asList}
                                                                    onChange={(e) => {
                                                                        touch();
                                                                        setChosen((current) => ({ ...current, [variable.source]: { ...current[variable.source], asList: e.target.checked } }));
                                                                    }}
                                                                />
                                                                {t('REGISTRATION.FORM.AS_LIST')}
                                                            </label>
                                                        )}
                                                    </div>
                                                )}
                                            </li>
                                        );
                                    })}
                                </ul>
                                {errors.variables && (
                                    <p id="registration-variables-error" className="text-xs font-medium text-[#A83434]">
                                        {errors.variables}
                                    </p>
                                )}
                                <p className="text-xs leading-relaxed text-black-600">{t('REGISTRATION.FORM.ALWAYS_SENT')}</p>
                            </fieldset>
                        </>
                    )}

                    <p className="max-w-[62ch] text-xs leading-relaxed text-black-700">{t('REGISTRATION.FORM.LATER_ONLY')}</p>

                    {general && (
                        <p role="alert" className="rounded-md border border-[#E5B9B9] bg-[#FBEFEF] px-3 py-2 text-sm text-[#7A2525]">
                            {general}
                        </p>
                    )}
                    <div className="flex flex-wrap items-center gap-3">
                        <Button type="submit" isLoading={saving} disabled={saving}>
                            {saving ? t('REGISTRATION.DIALOG.SAVING') : t('REGISTRATION.FORM.SAVE')}
                        </Button>
                        <p role="status" className="text-sm text-black-800">
                            {saved ? t('REGISTRATION.FORM.SAVED') : ''}
                        </p>
                    </div>
                </form>
            )}
        </section>
    );
}
