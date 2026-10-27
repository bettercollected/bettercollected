'use client';

import React, { FormEvent, useRef, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Field, inputClass } from '@app/components/registration/field';
import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@app/shadcn/components/ui/dialog';
import { RegistrationAuth, RegistrationKind, RegistrationService, RegistrationServiceInput, useCreateRegistrationServiceMutation, useUpdateRegistrationServiceMutation } from '@app/store/workspaces/registration-api';
import { errorCodeOf, errorKey, formatDay, isPlainToken, needsSecretAgain, serviceErrorField } from '@app/utils/registration';

type FieldName = 'name' | 'baseUrl' | 'objecttypesBaseUrl' | 'organisationName' | 'authName' | 'secret';

interface ServiceDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    workspaceId: string;
    /** Prefills the organisation name of a new service: what respondents read. */
    workspaceTitle?: string;
    /** The service being edited; none to add one. */
    service?: RegistrationService | null;
    onSaved?: (service: RegistrationService) => void;
}

const FIELD_ORDER: FieldName[] = ['name', 'baseUrl', 'objecttypesBaseUrl', 'organisationName', 'authName', 'secret'];

/**
 * Add or edit a case system: plain JSON to an address (Generic JSON) or an
 * Objects API. The secret (a password, a header value or the Objects API
 * token) is write-only: it is never prefilled or shown, an edit shows only "a
 * secret is set" with a Replace action, and changing the address or the
 * sign-in asks for it again. The kind is chosen when adding and then fixed.
 */
export default function ServiceDialog({ open, onOpenChange, workspaceId, workspaceTitle, service, onSaved }: ServiceDialogProps) {
    const { t } = useTranslation('builder');
    const title = service ? t('REGISTRATION.DIALOG.EDIT_TITLE', { name: service.name }) : t('REGISTRATION.DIALOG.ADD_TITLE');
    // The form lives only while the dialog is open: it starts fresh each time,
    // and what was typed (the secret above all) is gone when it closes.
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-h-[92dvh] max-w-lg overflow-y-auto bg-white" title={title}>
                <DialogHeader>
                    <DialogTitle>{title}</DialogTitle>
                    <DialogDescription>{!service ? t('REGISTRATION.DIALOG.INTRO_NEW') : service.kind === 'objects_api' ? t('REGISTRATION.DIALOG.INTRO_OBJECTS') : t('REGISTRATION.DIALOG.INTRO')}</DialogDescription>
                </DialogHeader>
                <ServiceForm onOpenChange={onOpenChange} workspaceId={workspaceId} workspaceTitle={workspaceTitle} service={service} onSaved={onSaved} />
            </DialogContent>
        </Dialog>
    );
}

function ServiceForm({ onOpenChange, workspaceId, workspaceTitle, service, onSaved }: Omit<ServiceDialogProps, 'open'>) {
    const { t, i18n } = useTranslation('builder');
    const editing = !!service;
    const [create, { isLoading: creating, reset: resetCreate }] = useCreateRegistrationServiceMutation();
    const [update, { isLoading: updating, reset: resetUpdate }] = useUpdateRegistrationServiceMutation();
    const saving = creating || updating;

    const [kind, setKind] = useState<RegistrationKind>(service?.kind ?? 'generic_json');
    const objects = kind === 'objects_api';
    const [name, setName] = useState(service?.name ?? '');
    const [baseUrl, setBaseUrl] = useState(service?.baseUrl ?? '');
    const [objecttypesBaseUrl, setObjecttypesBaseUrl] = useState(service?.objecttypesBaseUrl ?? '');
    const [organisationName, setOrganisationName] = useState(service?.organisationName ?? workspaceTitle ?? '');
    const [genericAuth, setAuth] = useState<RegistrationAuth>(service && service.kind === 'generic_json' ? service.auth : 'none');
    // The Objects API always signs in with its token.
    const auth: RegistrationAuth = objects ? 'token' : genericAuth;
    const [authName, setAuthName] = useState(service?.authName ?? '');
    const [secret, setSecret] = useState('');
    const [replacing, setReplacing] = useState(false);
    const [errors, setErrors] = useState<Partial<Record<FieldName, string>>>({});
    const [general, setGeneral] = useState<string | null>(null);
    const refs = useRef<Partial<Record<FieldName, HTMLInputElement | null>>>({});

    const changedCredentials = service ? needsSecretAgain(service, { baseUrl, auth, authName }) : false;
    const secretLabel = objects ? t('REGISTRATION.DIALOG.TOKEN') : auth === 'header' ? t('REGISTRATION.DIALOG.SECRET_HEADER') : t('REGISTRATION.DIALOG.SECRET_BASIC');
    // The secret field: always for a new service with a sign-in; for an edit
    // only on Replace, or when what it belongs to changed, or none is stored.
    const secretShown = auth !== 'none' && (!editing || replacing || changedCredentials || !service?.hasSecret);
    const secretStored = editing && auth !== 'none' && !!service?.hasSecret && !secretShown;

    const focusFirst = (found: Partial<Record<FieldName, string>>) => {
        const first = FIELD_ORDER.find((field) => found[field]);
        if (first) setTimeout(() => refs.current[first]?.focus(), 0);
    };

    const submit = async (event: FormEvent) => {
        event.preventDefault();
        const required = t('REGISTRATION.DIALOG.REQUIRED');
        const found: Partial<Record<FieldName, string>> = {};
        if (!name.trim()) found.name = required;
        if (!baseUrl.trim()) found.baseUrl = required;
        if (objects && !objecttypesBaseUrl.trim()) found.objecttypesBaseUrl = required;
        if (!organisationName.trim()) found.organisationName = required;
        if (!objects && auth !== 'none' && !authName.trim()) found.authName = required;
        if (secretShown && !secret) found.secret = t('REGISTRATION.ERROR.secret_required');
        else if (secretShown && objects && !isPlainToken(secret)) found.secret = t('REGISTRATION.ERROR.invalid_secret');
        setErrors(found);
        setGeneral(null);
        if (Object.keys(found).length) {
            focusFirst(found);
            return;
        }

        const body: RegistrationServiceInput = {};
        if (!service && objects) {
            Object.assign(body, { name: name.trim(), kind, baseUrl: baseUrl.trim(), objecttypesBaseUrl: objecttypesBaseUrl.trim(), organisationName: organisationName.trim() });
        } else if (!service) {
            Object.assign(body, { name: name.trim(), baseUrl: baseUrl.trim(), auth, organisationName: organisationName.trim() });
        } else if (objects) {
            // The token goes with the Objects API address; the object types address is never connected to.
            if (name.trim() !== service.name) body.name = name.trim();
            if (baseUrl.trim() !== service.baseUrl) body.baseUrl = baseUrl.trim();
            if (objecttypesBaseUrl.trim() !== (service.objecttypesBaseUrl ?? '')) body.objecttypesBaseUrl = objecttypesBaseUrl.trim();
            if (organisationName.trim() !== service.organisationName) body.organisationName = organisationName.trim();
        } else {
            // Only what changed: a changed address or sign-in is what asks for the secret again.
            if (name.trim() !== service.name) body.name = name.trim();
            if (baseUrl.trim() !== service.baseUrl) body.baseUrl = baseUrl.trim();
            if (auth !== service.auth) body.auth = auth;
            if (auth !== 'none' && authName.trim() !== (service.authName ?? '')) body.authName = authName.trim();
            if (organisationName.trim() !== service.organisationName) body.organisationName = organisationName.trim();
        }
        if (objects) {
            if (secretShown) body.secret = secret;
        } else if (auth !== 'none') {
            if (!service) body.authName = authName.trim();
            if (secretShown) body.secret = secret;
        }

        const response: any = service ? await update({ workspaceId, serviceId: service.id, body }) : await create({ workspaceId, body });
        // The request (secret included) must not stay in the query cache.
        resetCreate();
        resetUpdate();
        if (response.data) {
            setSecret('');
            onSaved?.(response.data);
            onOpenChange(false);
            return;
        }
        const code = errorCodeOf(response.error);
        const sentence = t(errorKey(code));
        const field = serviceErrorField(code, kind);
        if (field && (objects || field !== 'objecttypesBaseUrl')) {
            const next = { [field]: sentence };
            setErrors(next);
            focusFirst(next);
        } else if (objects && (code === 'invalid_url' || code === 'not_allowed' || code === 'unreachable')) {
            // The API does not say which of the two addresses it refused.
            setGeneral(`${sentence} ${t('REGISTRATION.ERROR.address_either')}`);
        } else {
            setGeneral(sentence);
        }
    };

    const bind = (field: FieldName) => (element: HTMLInputElement | null) => {
        refs.current[field] = element;
    };

    return (
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
            {editing ? (
                <div className="flex flex-col gap-1" data-testid="registration-service-kind-fixed">
                    <span className="text-sm font-medium text-black-900">{t('REGISTRATION.DIALOG.KIND')}</span>
                    <span className="text-sm text-black-800">{objects ? t('REGISTRATION.SERVICES.KIND_OBJECTS_API') : t('REGISTRATION.SERVICES.KIND_GENERIC_JSON')}</span>
                    <span className="text-xs text-black-600">{t('REGISTRATION.DIALOG.KIND_FIXED')}</span>
                </div>
            ) : (
                <Field id="registration-service-kind" label={t('REGISTRATION.DIALOG.KIND')}>
                    {(props) => (
                        <select
                            {...props}
                            className={inputClass}
                            value={kind}
                            onChange={(e) => {
                                setKind(e.target.value as RegistrationKind);
                                // A typed secret belongs to the kind it was typed for.
                                setSecret('');
                                setErrors({});
                            }}
                        >
                            <option value="generic_json">{t('REGISTRATION.DIALOG.KIND_GENERIC')}</option>
                            <option value="objects_api">{t('REGISTRATION.DIALOG.KIND_OBJECTS')}</option>
                        </select>
                    )}
                </Field>
            )}
            <Field id="registration-service-name" label={t('REGISTRATION.DIALOG.NAME')} hint={t('REGISTRATION.DIALOG.NAME_HINT')} error={errors.name}>
                {(props) => <input {...props} ref={bind('name')} className={inputClass} value={name} maxLength={80} autoComplete="off" onChange={(e) => setName(e.target.value)} />}
            </Field>
            <Field
                id="registration-service-url"
                label={objects ? t('REGISTRATION.DIALOG.OBJECTS_ADDRESS') : t('REGISTRATION.DIALOG.ADDRESS')}
                hint={objects ? t('REGISTRATION.DIALOG.OBJECTS_ADDRESS_HINT') : t('REGISTRATION.DIALOG.ADDRESS_HINT')}
                error={errors.baseUrl}
            >
                {(props) => <input {...props} ref={bind('baseUrl')} className={inputClass} type="url" inputMode="url" placeholder="https://" value={baseUrl} autoComplete="off" spellCheck={false} onChange={(e) => setBaseUrl(e.target.value)} />}
            </Field>
            {objects && (
                <Field id="registration-service-objecttypes-url" label={t('REGISTRATION.DIALOG.OBJECTTYPES_ADDRESS')} hint={t('REGISTRATION.DIALOG.OBJECTTYPES_ADDRESS_HINT')} error={errors.objecttypesBaseUrl}>
                    {(props) => (
                        <input
                            {...props}
                            ref={bind('objecttypesBaseUrl')}
                            className={inputClass}
                            type="url"
                            inputMode="url"
                            placeholder="https://"
                            value={objecttypesBaseUrl}
                            autoComplete="off"
                            spellCheck={false}
                            onChange={(e) => setObjecttypesBaseUrl(e.target.value)}
                        />
                    )}
                </Field>
            )}
            <Field id="registration-service-organisation" label={t('REGISTRATION.DIALOG.ORGANISATION')} hint={t('REGISTRATION.DIALOG.ORGANISATION_HINT')} error={errors.organisationName}>
                {(props) => <input {...props} ref={bind('organisationName')} className={inputClass} value={organisationName} maxLength={80} autoComplete="off" onChange={(e) => setOrganisationName(e.target.value)} />}
            </Field>
            {!objects && (
                <Field id="registration-service-auth" label={t('REGISTRATION.DIALOG.AUTH')}>
                    {(props) => (
                        <select {...props} className={inputClass} value={auth} onChange={(e) => setAuth(e.target.value as RegistrationAuth)}>
                            <option value="none">{t('REGISTRATION.DIALOG.AUTH_NONE')}</option>
                            <option value="header">{t('REGISTRATION.DIALOG.AUTH_HEADER')}</option>
                            <option value="basic">{t('REGISTRATION.DIALOG.AUTH_BASIC')}</option>
                        </select>
                    )}
                </Field>
            )}
            {!objects && auth !== 'none' && (
                <Field
                    id="registration-service-auth-name"
                    label={auth === 'header' ? t('REGISTRATION.DIALOG.AUTH_NAME_HEADER') : t('REGISTRATION.DIALOG.AUTH_NAME_BASIC')}
                    hint={auth === 'header' ? t('REGISTRATION.DIALOG.AUTH_NAME_HEADER_HINT') : undefined}
                    error={errors.authName}
                >
                    {(props) => <input {...props} ref={bind('authName')} className={inputClass} value={authName} maxLength={200} autoComplete="off" spellCheck={false} onChange={(e) => setAuthName(e.target.value)} />}
                </Field>
            )}
            {secretStored && (
                <div className="flex flex-col gap-1.5" data-testid="registration-secret-stored">
                    <span className="text-sm font-medium text-black-900">{secretLabel}</span>
                    <p className="text-sm text-black-700">{t(objects ? 'REGISTRATION.DIALOG.TOKEN_SET_ON' : 'REGISTRATION.DIALOG.SECRET_SET_ON', { date: formatDay(service?.secretSetAt, i18n.language) })}</p>
                    <div>
                        <Button type="button" variant="v2Button" size="sm" onClick={() => setReplacing(true)}>
                            {objects ? t('REGISTRATION.DIALOG.TOKEN_REPLACE') : t('REGISTRATION.DIALOG.SECRET_REPLACE')}
                        </Button>
                    </div>
                </div>
            )}
            {secretShown && (
                <Field
                    id="registration-service-secret"
                    label={secretLabel}
                    hint={editing && changedCredentials && service?.hasSecret ? t(objects ? 'REGISTRATION.DIALOG.TOKEN_AGAIN' : 'REGISTRATION.DIALOG.SECRET_AGAIN') : t(objects ? 'REGISTRATION.DIALOG.TOKEN_HINT' : 'REGISTRATION.DIALOG.SECRET_HINT')}
                    error={errors.secret}
                >
                    {(props) => <input {...props} ref={bind('secret')} className={inputClass} type="password" value={secret} autoComplete="new-password" spellCheck={false} onChange={(e) => setSecret(e.target.value)} />}
                </Field>
            )}
            {general && (
                <p role="alert" className="rounded-md border border-[#E5B9B9] bg-[#FBEFEF] px-3 py-2 text-sm text-[#7A2525]">
                    {general}
                </p>
            )}
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <Button type="button" variant="v2Button" onClick={() => onOpenChange(false)}>
                    {t('REGISTRATION.DIALOG.CANCEL')}
                </Button>
                <Button type="submit" isLoading={saving} disabled={saving}>
                    {saving ? t('REGISTRATION.DIALOG.SAVING') : t('REGISTRATION.DIALOG.SAVE')}
                </Button>
            </div>
        </form>
    );
}
