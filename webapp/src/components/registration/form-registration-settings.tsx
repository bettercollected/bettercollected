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
import {
    FormRegistration,
    FormRegistrationInput,
    RegistrationTestResult,
    RegistrationVariable,
    useCheckFormRegistrationMutation,
    useGetFormRegistrationQuery,
    useGetRegistrationServicesQuery,
    useGetRegistrationVariablesQuery,
    useSaveFormRegistrationMutation
} from '@app/store/workspaces/registration-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import {
    DEFAULT_REFERENCE_PATH,
    MAX_VARIABLES,
    canBeList,
    checkKey,
    defaultKeyOf,
    errorCodeOf,
    errorKey,
    findTargetConflict,
    formErrorField,
    formatTargetPath,
    isPlainPath,
    isValidKey,
    isValidObjectTypeVersion,
    objectTypeUrlProblem,
    parseTargetPath,
    referenceConflicts,
    variableReasonKey
} from '@app/utils/registration';

interface Chosen {
    /** Generic JSON: the name in the sent body. */
    key: string;
    asList: boolean;
    /** Objects API: `a.b.c`, where the answer goes in the object's data. */
    target: string;
}

type CheckState = 'checking' | { ok: boolean; code?: string | null; httpStatus?: number | null } | { error: string };

/** A file cannot be sent to an Objects API (it has no files in its records). */
const blockedFor = (variable: RegistrationVariable, objects: boolean) => objects && variable.type === 'file_upload';

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
    const [runCheck] = useCheckFormRegistrationMutation();

    const [on, setOn] = useState(false);
    const [serviceId, setServiceId] = useState('');
    const [path, setPath] = useState('');
    const [objectTypeUrl, setObjectTypeUrl] = useState('');
    const [objectTypeVersion, setObjectTypeVersion] = useState('');
    const [referencePath, setReferencePath] = useState(DEFAULT_REFERENCE_PATH);
    const [check, setCheck] = useState<CheckState | null>(null);
    const [dirty, setDirty] = useState(false);
    // What the last save answered: the check works on it at once, before the query refetches.
    const [savedRegistration, setSavedRegistration] = useState<FormRegistration | null>(null);
    const [chosen, setChosen] = useState<Record<string, Chosen>>({});
    const [dropped, setDropped] = useState(0);
    const [errors, setErrors] = useState<{ service?: string; path?: string; variables?: string; objectType?: string; version?: string; reference?: string }>({});
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
            next[mapping.source] = { key: mapping.key ?? '', asList: list.has(mapping.source), target: formatTargetPath(mapping.targetPath) };
        });
        setOn(registration.enabled);
        setServiceId(registration.serviceId ?? '');
        setPath(registration.path ?? '');
        setObjectTypeUrl(registration.objectTypeUrl ?? '');
        setObjectTypeVersion(registration.objectTypeVersion ? String(registration.objectTypeVersion) : '');
        setReferencePath(registration.referencePath?.length ? formatTargetPath(registration.referencePath) : DEFAULT_REFERENCE_PATH);
        setChosen(next);
        setDropped(missing);
    }, [registration, variables, formId]);

    const services = servicesQuery.data ?? [];
    const loading = registrationQuery.isLoading || variablesQuery.isLoading || servicesQuery.isLoading;
    const loadFailed = registrationQuery.isError || variablesQuery.isError;
    const selectedService = useMemo(() => services.find((s) => s.id === serviceId), [services, serviceId]);

    const objects = (selectedService?.kind ?? (serviceId === registration?.serviceId ? registration?.kind : null)) === 'objects_api';

    const touch = () => {
        setSaved(false);
        setDirty(true);
        setCheck(null);
    };

    const toggleVariable = (source: string, checked: boolean) => {
        touch();
        setChosen((current) => {
            const next = { ...current };
            if (checked) next[source] = { key: '', asList: false, target: '' };
            else delete next[source];
            return next;
        });
    };

    /**
     * The body of a save that switches sending off: the draft as it stands, without the
     * client checks of a switch-on. Fragments the server would refuse as malformed (a
     * half-typed address or path, a repeated name) are left out rather than sent, so
     * switching off never gets stuck on a field that is not even on screen; whatever the
     * server still refuses is shown.
     */
    const offBody = (): FormRegistrationInput => {
        // The server takes at most MAX_VARIABLES variables; a form with more questions than that keeps the first ones here.
        const rows = (variables ?? []).filter((v) => chosen[v.source] && !blockedFor(v, objects)).slice(0, MAX_VARIABLES);
        if (objects) {
            const parsedReference = referencePath.trim() ? parseTargetPath(referencePath) : [DEFAULT_REFERENCE_PATH];
            return {
                enabled: false,
                serviceId: serviceId || null,
                path: '',
                variables: rows.flatMap((v) => {
                    const target = parseTargetPath(chosen[v.source].target);
                    return target ? [{ source: v.source, targetPath: target }] : [];
                }),
                transformToList: [],
                objectTypeUrl: objectTypeUrl.trim() && !objectTypeUrlProblem(objectTypeUrl) ? objectTypeUrl.trim() : null,
                objectTypeVersion: isValidObjectTypeVersion(objectTypeVersion) ? Number(objectTypeVersion) : null,
                referencePath: parsedReference ?? [DEFAULT_REFERENCE_PATH]
            };
        }
        const names = new Set<string>();
        const kept = rows.filter((v) => {
            const name = chosen[v.source].key.trim() || defaultKeyOf(v.source);
            if (!isValidKey(name) || names.has(name)) return false;
            names.add(name);
            return true;
        });
        return {
            enabled: false,
            serviceId: serviceId || null,
            path: isPlainPath(path.trim()) ? path.trim() : '',
            variables: kept.map((v) => ({ source: v.source, key: chosen[v.source].key.trim() || undefined })),
            transformToList: kept.filter((v) => chosen[v.source].asList && canBeList(v)).map((v) => v.source)
        };
    };

    const submit = async (event: React.FormEvent) => {
        event.preventDefault();
        setSaved(false);
        setGeneral(null);
        if (!on) {
            // Turning it off never waits on the draft: an out-of-date object type address
            // or half-filled paths must not keep sending switched on. The settings as the
            // user last saw them go along, so they are still there when it is switched on
            // again (the server checks them then). Only what can never be stored is left out.
            setErrors({});
            setKeyErrors({});
            const off: any = await save({ workspaceId, formId, body: offBody() });
            if (off.data) {
                setSaved(true);
                setDirty(false);
                setSavedRegistration(off.data);
                setDropped(0);
            } else {
                setGeneral(t(errorKey(errorCodeOf(off.error))));
            }
            return;
        }
        const sources = (variables ?? []).filter((v) => chosen[v.source] && !blockedFor(v, objects)).map((v) => v.source);
        const found: typeof errors = {};
        const keyProblems: Record<string, string> = {};
        const targets: Record<string, string[]> = {};
        let reference: string[] = [];
        if (on) {
            if (!serviceId) found.service = t('REGISTRATION.ERROR.service_required');
            if (sources.length === 0) found.variables = t('REGISTRATION.ERROR.variables_required');
        }
        if (objects) {
            // Checked here for a quick answer; the server decides.
            if (!objectTypeUrl.trim()) {
                if (on) found.objectType = t('REGISTRATION.ERROR.object_type_required');
            } else {
                const problem = objectTypeUrlProblem(objectTypeUrl, selectedService?.objecttypesBaseUrl);
                if (problem) found.objectType = t(errorKey(problem));
            }
            if (!objectTypeVersion.trim()) {
                if (on && !found.objectType) found.objectType = t('REGISTRATION.ERROR.object_type_required');
            } else if (!isValidObjectTypeVersion(objectTypeVersion)) {
                found.version = t('REGISTRATION.ERROR.invalid_object_type_version');
            }
            const parsedReference = referencePath.trim() ? parseTargetPath(referencePath) : [DEFAULT_REFERENCE_PATH];
            if (!parsedReference) found.reference = t('REGISTRATION.ERROR.invalid_reference_path');
            else reference = parsedReference;
            sources.forEach((source) => {
                const parsed = parseTargetPath(chosen[source].target);
                if (!parsed) keyProblems[source] = t('REGISTRATION.ERROR.invalid_target_path');
                else targets[source] = parsed;
            });
            if (!Object.keys(keyProblems).length) {
                const conflict = findTargetConflict(sources.map((source) => ({ source, path: targets[source] })));
                if (conflict) keyProblems[conflict.second] = t('REGISTRATION.FORM.TARGET_TAKEN');
                else if (!found.reference && referenceConflicts(reference, Object.values(targets))) found.reference = t('REGISTRATION.ERROR.reference_path_conflict');
            }
        } else if (on) {
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
        if (Object.keys(found).length || Object.keys(keyProblems).length) {
            // never a silent stop: say so, next to the fields that are marked
            setGeneral(t('REGISTRATION.FORM.FIX_ERRORS'));
            return;
        }

        const response: any = await save({
            workspaceId,
            formId,
            body: objects
                ? {
                      enabled: on,
                      serviceId: serviceId || null,
                      path: '',
                      variables: sources.map((source) => ({ source, targetPath: targets[source] })),
                      transformToList: [],
                      objectTypeUrl: objectTypeUrl.trim() || null,
                      objectTypeVersion: objectTypeVersion.trim() ? Number(objectTypeVersion) : null,
                      referencePath: reference
                  }
                : {
                      enabled: on,
                      serviceId: serviceId || null,
                      path: path.trim(),
                      variables: sources.map((source) => ({ source, key: chosen[source].key.trim() || undefined })),
                      transformToList: sources.filter((source) => chosen[source].asList && canBeList(variables!.find((v) => v.source === source)!))
                  }
        });
        if (response.data) {
            setSaved(true);
            setDirty(false);
            setSavedRegistration(response.data);
            setDropped(0);
            return;
        }
        const code = errorCodeOf(response.error);
        const sentence = t(errorKey(code));
        const field = formErrorField(code);
        // Fields of the Objects API settings are on screen only for that kind.
        if (field && (objects || !['objectType', 'version', 'reference'].includes(field))) setErrors({ [field]: sentence });
        else setGeneral(sentence);
    };

    const runConnectionCheck = async () => {
        setCheck('checking');
        const response: any = await runCheck({ workspaceId, formId });
        // 429 (rate_limited) and the rest arrive as an error with our code.
        setCheck(response.data ? (response.data as RegistrationTestResult) : { error: errorCodeOf(response.error) });
    };

    const checkText = (state: CheckState | null) => {
        if (!state) return '';
        if (state === 'checking') return t('REGISTRATION.FORM.CHECKING');
        if ('error' in state) return t(state.error === 'rate_limited' ? 'REGISTRATION.CHECK.rate_limited' : errorKey(state.error));
        return t(checkKey(state.ok, state.code), { status: state.httpStatus ?? '' });
    };
    const checkFailed = !!check && check !== 'checking' && ('error' in check || !check.ok);

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
                            {selectedService && <p className="-mt-3 text-xs text-black-600">{t(objects ? 'REGISTRATION.FORM.SENDS_TO_OBJECTS' : 'REGISTRATION.FORM.SENDS_TO', { address: selectedService.baseUrl })}</p>}

                            {objects && (
                                <>
                                    <div className="flex max-w-[62ch] flex-col gap-1 text-xs leading-relaxed text-black-600">
                                        <p>{t('REGISTRATION.FORM.OBJECTS_HELP')}</p>
                                        <p>{t('REGISTRATION.FORM.OBJECTS_EDGE')}</p>
                                    </div>
                                    <Field id="registration-form-object-type" label={t('REGISTRATION.FORM.OBJECT_TYPE_URL')} hint={t('REGISTRATION.FORM.OBJECT_TYPE_URL_HINT', { base: selectedService?.objecttypesBaseUrl ?? '' })} error={errors.objectType}>
                                        {(props) => (
                                            <input
                                                {...props}
                                                className={inputClass}
                                                value={objectTypeUrl}
                                                maxLength={1000}
                                                placeholder="https://"
                                                autoComplete="off"
                                                spellCheck={false}
                                                onChange={(e) => {
                                                    touch();
                                                    setObjectTypeUrl(e.target.value);
                                                }}
                                            />
                                        )}
                                    </Field>
                                    <Field id="registration-form-object-type-version" label={t('REGISTRATION.FORM.OBJECT_TYPE_VERSION')} hint={t('REGISTRATION.FORM.OBJECT_TYPE_VERSION_HINT')} error={errors.version}>
                                        {(props) => (
                                            <input
                                                {...props}
                                                className={inputClass + ' sm:max-w-40'}
                                                inputMode="numeric"
                                                value={objectTypeVersion}
                                                maxLength={5}
                                                autoComplete="off"
                                                onChange={(e) => {
                                                    touch();
                                                    setObjectTypeVersion(e.target.value);
                                                }}
                                            />
                                        )}
                                    </Field>
                                    <Field id="registration-form-reference-path" label={t('REGISTRATION.FORM.REFERENCE_PATH')} hint={t('REGISTRATION.FORM.REFERENCE_PATH_HINT')} error={errors.reference}>
                                        {(props) => (
                                            <input
                                                {...props}
                                                className={inputClass}
                                                value={referencePath}
                                                placeholder={DEFAULT_REFERENCE_PATH}
                                                autoComplete="off"
                                                spellCheck={false}
                                                onChange={(e) => {
                                                    touch();
                                                    setReferencePath(e.target.value);
                                                }}
                                            />
                                        )}
                                    </Field>
                                </>
                            )}

                            {!objects && (
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
                            )}

                            <fieldset className="flex flex-col gap-2" aria-describedby={errors.variables ? 'registration-variables-error' : 'registration-variables-hint'}>
                                <legend className="text-sm font-medium text-black-900">{t('REGISTRATION.FORM.VARIABLES')}</legend>
                                <p id="registration-variables-hint" className="text-xs leading-relaxed text-black-600">
                                    {objects ? t('REGISTRATION.FORM.VARIABLES_HINT_OBJECTS') : t('REGISTRATION.FORM.VARIABLES_HINT')}
                                </p>
                                {dropped > 0 && (
                                    <p role="status" className="text-xs text-black-700">
                                        {t('REGISTRATION.FORM.DROPPED', { count: dropped })}
                                    </p>
                                )}
                                {variables.length === 0 && <p className="text-sm text-black-700">{t('REGISTRATION.FORM.NO_VARIABLES')}</p>}
                                <ul className="flex flex-col divide-y divide-black-200 rounded-md border border-black-300">
                                    {variables.map((variable, index) => {
                                        const row = blockedFor(variable, objects) ? undefined : chosen[variable.source];
                                        // by position: a source can hold characters an id cannot
                                        const checkboxId = `registration-var-${index}`;
                                        const keyId = `${checkboxId}-key`;
                                        const keyError = keyErrors[variable.source];
                                        const blocked = blockedFor(variable, objects);
                                        const choosable = variable.supported && !blocked;
                                        return (
                                            <li key={variable.source} className="flex flex-col gap-2 px-3 py-2.5" data-testid={`registration-variable-${variable.source}`}>
                                                <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
                                                    <div className="flex min-w-0 items-start gap-2.5">
                                                        <input
                                                            id={checkboxId}
                                                            type="checkbox"
                                                            className="mt-0.5 h-4 w-4 shrink-0 accent-brand-500"
                                                            checked={!!row}
                                                            disabled={!choosable}
                                                            aria-describedby={!choosable ? `${checkboxId}-reason` : undefined}
                                                            onChange={(e) => toggleVariable(variable.source, e.target.checked)}
                                                        />
                                                        <label htmlFor={checkboxId} className={choosable ? 'text-sm break-words text-black-900' : 'text-sm break-words text-black-600'}>
                                                            {variable.label}
                                                        </label>
                                                    </div>
                                                    <span className="text-xs text-black-600">
                                                        {variable.type.replace(/_/g, ' ')}
                                                        {!choosable && (
                                                            <>
                                                                {' · '}
                                                                <span id={`${checkboxId}-reason`}>{blocked ? t('REGISTRATION.FORM.REASON.file_upload') : t(variableReasonKey(variable.reason))}</span>
                                                            </>
                                                        )}
                                                    </span>
                                                </div>
                                                {row && (
                                                    <div className="ml-6 flex flex-col gap-2 sm:flex-row sm:items-start">
                                                        <div className="flex flex-1 flex-col gap-1">
                                                            <label htmlFor={keyId} className="text-xs font-medium text-black-700">
                                                                {objects ? t('REGISTRATION.FORM.TARGET_PATH') : t('REGISTRATION.FORM.KEY')}
                                                            </label>
                                                            <input
                                                                id={keyId}
                                                                className={inputClass}
                                                                value={objects ? row.target : row.key}
                                                                maxLength={objects ? 600 : 64}
                                                                autoComplete="off"
                                                                spellCheck={false}
                                                                placeholder={objects ? 'a.b.c' : defaultKeyOf(variable.source)}
                                                                aria-invalid={!!keyError}
                                                                aria-describedby={keyError ? `${keyId}-error` : undefined}
                                                                onChange={(e) => {
                                                                    touch();
                                                                    setChosen((current) => ({ ...current, [variable.source]: { ...current[variable.source], ...(objects ? { target: e.target.value } : { key: e.target.value }) } }));
                                                                }}
                                                            />
                                                            {keyError && (
                                                                <p id={`${keyId}-error`} className="text-xs font-medium text-[#A83434]">
                                                                    {keyError}
                                                                </p>
                                                            )}
                                                        </div>
                                                        {!objects && canBeList(variable) && (
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
                                {!objects && <p className="text-xs leading-relaxed text-black-600">{t('REGISTRATION.FORM.ALWAYS_SENT')}</p>}
                            </fieldset>
                        </>
                    )}

                    <p className="max-w-[62ch] text-xs leading-relaxed text-black-700">{t('REGISTRATION.FORM.LATER_ONLY')}</p>

                    {general && (
                        <p role="alert" className="rounded-md border border-[#E5B9B9] bg-[#FBEFEF] px-3 py-2 text-sm text-[#7A2525]">
                            {general}
                        </p>
                    )}
                    {on && objects && (
                        <div className="flex flex-col gap-2 rounded-md border border-black-300 p-3" data-testid="registration-check">
                            <div className="flex flex-wrap items-center gap-3">
                                <Button type="button" variant="v2Button" isLoading={check === 'checking'} disabled={check === 'checking' || dirty || !(savedRegistration ?? registration).serviceId} onClick={runConnectionCheck}>
                                    {check === 'checking' ? t('REGISTRATION.FORM.CHECKING') : t('REGISTRATION.FORM.CHECK')}
                                </Button>
                                <p id="registration-check-hint" className="text-xs text-black-600">
                                    {dirty ? t('REGISTRATION.FORM.CHECK_SAVE_FIRST') : t('REGISTRATION.FORM.CHECK_HINT')}
                                </p>
                            </div>
                            <p role="status" data-testid="registration-check-result" className={checkFailed ? 'text-sm font-medium text-[#A83434]' : 'text-sm text-black-800'}>
                                {check === 'checking' ? '' : checkText(check)}
                            </p>
                        </div>
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
