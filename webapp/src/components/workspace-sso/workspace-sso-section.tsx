'use client';

import { FormEvent, useState } from 'react';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

import { AlertTriangle, Check, CircleCheck, Copy, KeyRound, LifeBuoy, ShieldCheck } from 'lucide-react';
import { Trans, useTranslation } from 'react-i18next';

import { useIntlLocale } from '@app/lib/hooks/use-intl-locale';

import SsoSelfHostingGuide from '@app/components/workspace-sso/sso-self-hosting-guide';
import environments from '@app/configs/environments';
import { sso } from '@app/constants/locales/sso';
import { navigateWithReferrer, ssoTestMessage } from '@app/lib/sso';
import { workspaceSectionUrls } from '@app/lib/workspace-sections';
import { SsoConnectionDto, SsoConnectionType, SsoOverviewDto, SsoServiceProviderDto } from '@app/models/dtos/workspace-sso-dto';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { useAppSelector } from '@app/store/hooks';
import { useCreateSsoConnectionMutation, useDeleteSsoConnectionMutation, useGetWorkspaceSsoQuery, useSetSsoConnectionEnabledMutation, useUpdateSsoSettingsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export const inputClass = 'h-10 w-full rounded-md border border-control bg-white px-3.5 py-0 text-sm text-black-900 outline-hidden transition duration-150 placeholder:text-black-600 focus:border-brand-500';

export const ROLE_LABELS: Record<string, string> = {
    ADMIN: 'Admin',
    COLLABORATOR: 'Collaborator',
    VIEWER: 'Viewer',
    EDITOR: 'Editor',
    REVIEWER: 'Reviewer',
    PRIVACY_OFFICER: 'Privacy officer'
};

/** A role's name in the dashboard's language (the role keys the members screens use), else the English label. */
export function roleLabel(role: string, t: (key: string, options?: any) => string): string {
    if (role === 'COLLABORATOR') return t('SSO_UI.ROLE_COLLABORATOR');
    return ROLE_LABELS[role] ? t(`WORKSPACE_ROLES.${role}.NAME`) : role;
}

export function errorMessage(error: any, fallback: string): string {
    const data = error?.data;
    if (data && typeof data === 'object' && typeof data.message === 'string') return data.message;
    if (typeof data === 'string') return data;
    return fallback;
}

export function formatTime(value?: string | null, locale?: string): string {
    return value ? new Date(value).toLocaleString(locale) : '';
}

export function CopyField({ label, value, hint }: { label: string; value: string; hint?: string }) {
    const { t } = useTranslation();
    const [copied, setCopied] = useState(false);
    return (
        <div className="flex flex-col gap-1">
            <span className="text-[11px] font-medium uppercase tracking-wide text-black-600">{label}</span>
            <div className="flex items-center justify-between gap-3 rounded-md border border-black-300 bg-white px-3 py-2">
                <code className="break-all text-[13px] text-black-800">{value}</code>
                <button
                    type="button"
                    aria-label={t('SSO_UI.COPY', { label })}
                    onClick={async () => {
                        try {
                            await navigator.clipboard.writeText(value);
                            setCopied(true);
                            setTimeout(() => setCopied(false), 1500);
                        } catch {
                            setCopied(false);
                        }
                    }}
                    className="shrink-0 rounded p-1 text-black-600 transition-colors hover:text-black-800"
                >
                    {copied ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
                    <span className="sr-only" aria-live="polite">
                        {copied ? t('SSO_UI.COPIED') : ''}
                    </span>
                </button>
            </div>
            {hint && <span className="text-[11px] text-black-600">{hint}</span>}
        </div>
    );
}

export function Section({ title, description, children }: { title: string; description?: React.ReactNode; children: React.ReactNode }) {
    return (
        <section className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
                <h2 className="text-sm font-semibold text-black-900">{title}</h2>
                {description && <p className="max-w-[62ch] text-xs leading-relaxed text-black-600">{description}</p>}
            </div>
            {children}
        </section>
    );
}

/** What the last failed test saw: the domain of the address the identity
 * provider sent (never the address) and the names of the claims it sent. */
export function TestDiagnostics({ connection, domains }: { connection: SsoConnectionDto; domains: string[] }) {
    const { t } = useTranslation();
    const domain = connection.lastTestDomain;
    const claims = connection.lastTestClaims ?? [];
    if (!domain && claims.length === 0) return null;
    return (
        <span className="flex flex-col gap-0.5 text-xs text-black-700">
            {domain && (
                <span>
                    <Trans i18nKey="SSO_UI.DIAG_ADDRESS" values={{ domain, domains: domains.length ? domains.join(', ') : t('SSO_UI.DIAG_NONE_YET') }} components={{ 1: <strong className="break-all" /> }} />
                </span>
            )}
            {claims.length > 0 && (
                <span>
                    <Trans i18nKey="SSO_UI.DIAG_CLAIMS" values={{ claims: claims.join(', ') }} components={{ 1: <code className="break-all text-[11px]" /> }} />
                </span>
            )}
        </span>
    );
}

function ConnectionCard({ connection, workspaceId, ssoRequired, canManage, domains }: { connection: SsoConnectionDto; workspaceId: string; ssoRequired: boolean; canManage: boolean; domains: string[] }) {
    const { t } = useTranslation();
    const locale = useIntlLocale();
    const { toast } = useToast();
    const [setEnabled, { isLoading: isToggling }] = useSetSsoConnectionEnabledMutation();
    const [deleteConnection, { isLoading: isDeleting }] = useDeleteSsoConnectionMutation();
    const enabled = connection.status === 'enabled';
    const locked = enabled && ssoRequired;

    const toggle = async () => {
        const response: any = await setEnabled({ workspace_id: workspaceId, connection_id: connection.id, enabled: !enabled });
        if (response.error) toast({ description: errorMessage(response.error, t('SSO_UI.CHANGE_FAILED')), variant: 'destructive' });
    };

    const remove = async () => {
        if (!window.confirm(t('SSO_UI.DELETE_CONFIRM', { name: connection.name }))) return;
        const response: any = await deleteConnection({ workspace_id: workspaceId, connection_id: connection.id });
        if (response.error) toast({ description: errorMessage(response.error, t('SSO_UI.DELETE_FAILED')), variant: 'destructive' });
        else toast({ description: t('SSO_UI.DELETED', { name: connection.name }) });
    };

    const test = () => navigateWithReferrer(`${environments.API_ENDPOINT_HOST}/workspaces/${workspaceId}/sso/connections/${connection.id}/test`);

    return (
        <li className="flex flex-col gap-3 rounded border border-black-300 bg-white p-4" data-testid={`sso-connection-${connection.id}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 flex-col gap-1">
                    <div className="flex flex-wrap items-center gap-2">
                        <KeyRound className={cn('h-4 w-4 shrink-0', enabled ? 'text-success' : 'text-black-600')} />
                        <span className="break-all text-sm font-semibold text-black-900">{connection.name}</span>
                        <span className="rounded bg-black-100 px-1.5 py-0.5 text-[11px] font-medium uppercase text-black-600">{connection.type}</span>
                        <span className={cn('rounded px-1.5 py-0.5 text-[11px] font-medium', enabled ? 'bg-[#E7F6EE] text-success-700' : 'bg-black-100 text-black-600')}>{enabled ? t('SSO_UI.ENABLED') : t('SSO_UI.DISABLED')}</span>
                        {connection.tested ? (
                            <span className="rounded bg-[#E7F6EE] px-1.5 py-0.5 text-[11px] font-medium text-success-700">{t('SSO_UI.TESTED')}</span>
                        ) : (
                            <span className="rounded bg-[#FDF3E3] px-1.5 py-0.5 text-[11px] font-medium text-[#9A5B00]">{t('SSO_UI.NOT_TESTED')}</span>
                        )}
                    </div>
                    <span className="break-all text-xs text-black-600">
                        {connection.idpEntityId || connection.oidcDiscoveryUrl || connection.metadataUrl || ''}
                        {connection.oidcClientId ? ` · ${t('SSO_UI.CLIENT', { id: connection.oidcClientId })}` : ''}
                    </span>
                    <span className="text-xs text-black-600">{connection.testedAt ? t('SSO_UI.LAST_TEST_OK', { time: formatTime(connection.testedAt, locale) }) : t('SSO_UI.TEST_FIRST')}</span>
                    {connection.lastTestError && <span className="text-xs text-[#C43D3D]">{t('SSO_UI.LAST_TEST_FAILED', { message: ssoTestMessage(connection.lastTestError, t) })}</span>}
                    {connection.lastTestError && <TestDiagnostics connection={connection} domains={domains} />}
                    {connection.type === 'oidc' && (
                        <span className="text-xs text-black-600">
                            <Trans i18nKey="SSO_UI.OIDC_NOTE" components={{ 1: <code className="break-all text-[11px]" /> }} />
                        </span>
                    )}
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                    <Button size="sm" variant="v2Button" onClick={test}>
                        {t('SSO_UI.TEST')}
                    </Button>
                    {canManage && (
                        <>
                            <Button
                                size="sm"
                                variant={enabled ? 'v2Button' : 'primary'}
                                isLoading={isToggling}
                                disabled={locked || (!enabled && !connection.tested)}
                                onClick={toggle}
                                title={locked ? t('SSO_UI.TURN_OFF_REQUIRED_FIRST') : !enabled && !connection.tested ? t('SSO_UI.TEST_SUCCESS_FIRST') : undefined}
                            >
                                {enabled ? t('SSO_UI.DISABLE') : t('SSO_UI.ENABLE')}
                            </Button>
                            <Button size="sm" variant="dangerGhost" isLoading={isDeleting} disabled={locked} onClick={remove} aria-label={t('SSO_UI.DELETE_ARIA', { name: connection.name })}>
                                {t('SSO_UI.DELETE')}
                            </Button>
                        </>
                    )}
                </div>
            </div>
        </li>
    );
}

function DomainsLink({ workspaceName }: { workspaceName?: string }) {
    const { t } = useTranslation();
    return (
        <Link className="text-brand-500 underline" href={workspaceSectionUrls(workspaceName).domains}>
            {t('SSO_UI.VERIFY_DOMAIN_LINK')}
        </Link>
    );
}

function AddConnectionForm({ workspaceId, workspaceName, onDone }: { workspaceId: string; workspaceName?: string; onDone: () => void }) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const [create, { isLoading }] = useCreateSsoConnectionMutation();
    const [type, setType] = useState<SsoConnectionType>('saml');
    const [source, setSource] = useState<'url' | 'xml'>('url');
    const [name, setName] = useState('');
    const [metadataUrl, setMetadataUrl] = useState('');
    const [metadataXml, setMetadataXml] = useState('');
    const [discoveryUrl, setDiscoveryUrl] = useState('');
    const [clientId, setClientId] = useState('');
    const [clientSecret, setClientSecret] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [needsDomain, setNeedsDomain] = useState(false);

    const submit = async (event: FormEvent) => {
        event.preventDefault();
        setError(null);
        setNeedsDomain(false);
        const body =
            type === 'saml'
                ? { type, name: name.trim() || undefined, ...(source === 'url' ? { metadataUrl: metadataUrl.trim() } : { metadataXml: metadataXml.trim() }) }
                : { type, name: name.trim() || undefined, discoveryUrl: discoveryUrl.trim(), clientId: clientId.trim(), clientSecret };
        const response: any = await create({ workspace_id: workspaceId, body });
        if (response.error) {
            setError(errorMessage(response.error, t('SSO_UI.CREATE_FAILED')));
            setNeedsDomain(response.error?.data?.code === 'sso_domain_required');
            return;
        }
        setClientSecret('');
        toast({ description: t('SSO_UI.CREATED') });
        onDone();
    };

    return (
        <form onSubmit={submit} className="flex flex-col gap-4 rounded border border-black-300 bg-white p-4" noValidate>
            <fieldset className="flex flex-wrap gap-4">
                <legend className="mb-2 text-xs font-semibold text-black-800">{t('SSO_UI.PROTOCOL')}</legend>
                {(['saml', 'oidc'] as SsoConnectionType[]).map((value) => (
                    <label key={value} className="flex items-center gap-2 text-sm text-black-800">
                        <input type="radio" name="sso-type" value={value} checked={type === value} onChange={() => setType(value)} />
                        {value === 'saml' ? t('SSO_UI.SAML') : t('SSO_UI.OIDC')}
                    </label>
                ))}
            </fieldset>
            <label className="flex flex-col gap-1 text-xs font-medium text-black-800">
                {t('SSO_UI.NAME_OPTIONAL')}
                <input className={inputClass} value={name} maxLength={100} placeholder={type === 'saml' ? 'Okta' : 'Microsoft Entra ID'} onChange={(e) => setName(e.target.value)} />
            </label>
            {type === 'saml' ? (
                <>
                    <fieldset className="flex flex-wrap gap-4">
                        <legend className="mb-2 text-xs font-semibold text-black-800">{t('SSO_UI.METADATA_SECTION')}</legend>
                        <label className="flex items-center gap-2 text-sm text-black-800">
                            <input type="radio" name="sso-source" checked={source === 'url'} onChange={() => setSource('url')} />
                            {t('SSO_UI.METADATA_URL')}
                        </label>
                        <label className="flex items-center gap-2 text-sm text-black-800">
                            <input type="radio" name="sso-source" checked={source === 'xml'} onChange={() => setSource('xml')} />
                            {t('SSO_UI.METADATA_PASTE')}
                        </label>
                    </fieldset>
                    {source === 'url' ? (
                        <label className="flex flex-col gap-1 text-xs font-medium text-black-800">
                            {t('SSO_UI.METADATA_URL')}
                            <input className={inputClass} type="url" value={metadataUrl} placeholder="https://idp.example.com/app/metadata" onChange={(e) => setMetadataUrl(e.target.value)} />
                            <span className="font-normal text-black-600">{t('SSO_UI.METADATA_HTTPS')}</span>
                        </label>
                    ) : (
                        <label className="flex flex-col gap-1 text-xs font-medium text-black-800">
                            {t('SSO_UI.METADATA_XML')}
                            <textarea className={cn(inputClass, 'h-40 py-2 font-mono text-xs')} value={metadataXml} placeholder="<md:EntityDescriptor …>" onChange={(e) => setMetadataXml(e.target.value)} spellCheck={false} />
                        </label>
                    )}
                </>
            ) : (
                <>
                    <label className="flex flex-col gap-1 text-xs font-medium text-black-800">
                        {t('SSO_UI.DISCOVERY_URL')}
                        <input className={inputClass} type="url" value={discoveryUrl} placeholder="https://login.example.com/.well-known/openid-configuration" onChange={(e) => setDiscoveryUrl(e.target.value)} />
                    </label>
                    <label className="flex flex-col gap-1 text-xs font-medium text-black-800">
                        {t('SSO_UI.CLIENT_ID')}
                        <input className={inputClass} value={clientId} autoComplete="off" onChange={(e) => setClientId(e.target.value)} />
                    </label>
                    <label className="flex flex-col gap-1 text-xs font-medium text-black-800">
                        {t('SSO_UI.CLIENT_SECRET')}
                        <input className={inputClass} type="password" value={clientSecret} autoComplete="new-password" onChange={(e) => setClientSecret(e.target.value)} />
                        <span className="font-normal text-black-600">{t('SSO_UI.CLIENT_SECRET_HINT')}</span>
                    </label>
                </>
            )}
            {error && (
                <p role="alert" className="text-xs text-[#C43D3D]">
                    {error}
                    {needsDomain && (
                        <>
                            {' '}
                            <DomainsLink workspaceName={workspaceName} />.
                        </>
                    )}
                </p>
            )}
            <div className="flex gap-2">
                <Button type="submit" size="sm" variant="primary" isLoading={isLoading}>
                    {t('SSO_UI.CREATE')}
                </Button>
                <Button type="button" size="sm" variant="v2Button" onClick={onDone}>
                    {t('SSO_UI.CANCEL')}
                </Button>
            </div>
        </form>
    );
}

function HelpStep({ children }: { children: React.ReactNode }) {
    return <li className="leading-relaxed">{children}</li>;
}

function Value({ children }: { children?: React.ReactNode }) {
    return <code className="break-all rounded bg-black-100 px-1 py-0.5 text-[11px] text-black-800">{children}</code>;
}

/** Step-by-step setup for Microsoft Entra ID (and a short Keycloak note),
 * with this instance's own service-provider values. */
export function EntraSetupHelp({ sp }: { sp: SsoServiceProviderDto }) {
    const { t } = useTranslation();
    const v = { v: <Value /> };
    return (
        <details className="group rounded-md border border-black-300 bg-white p-3 text-xs text-black-700" data-testid="sso-entra-help">
            <summary className="cursor-pointer text-xs font-semibold text-black-900">{t('SSO_UI.ENTRA_TITLE')}</summary>
            <div className="mt-3 flex flex-col gap-4">
                <div className="flex flex-col gap-1.5">
                    <h3 className="text-xs font-semibold text-black-900">{t('SSO_UI.ENTRA_SAML')}</h3>
                    <ol className="ml-4 list-decimal space-y-1">
                        <HelpStep>{t('SSO_UI.ENTRA_SAML_1')}</HelpStep>
                        <HelpStep>
                            <Trans i18nKey="SSO_UI.ENTRA_SAML_2" values={{ entityId: sp.entityId, acsUrl: sp.acsUrl }} components={v} />
                        </HelpStep>
                        <HelpStep>
                            <Trans i18nKey="SSO_UI.ENTRA_SAML_3" components={v} />
                        </HelpStep>
                        <HelpStep>{t('SSO_UI.ENTRA_SAML_4')}</HelpStep>
                        <HelpStep>{t('SSO_UI.ENTRA_SAML_5')}</HelpStep>
                    </ol>
                </div>
                <div className="flex flex-col gap-1.5">
                    <h3 className="text-xs font-semibold text-black-900">{t('SSO_UI.ENTRA_OIDC')}</h3>
                    <ol className="ml-4 list-decimal space-y-1">
                        <HelpStep>
                            <Trans i18nKey="SSO_UI.ENTRA_OIDC_1" values={{ uri: sp.oidcRedirectUri }} components={v} />
                        </HelpStep>
                        <HelpStep>{t('SSO_UI.ENTRA_OIDC_2')}</HelpStep>
                        <HelpStep>{t('SSO_UI.ENTRA_OIDC_3')}</HelpStep>
                        <HelpStep>
                            <Trans i18nKey="SSO_UI.ENTRA_OIDC_4" components={v} />
                        </HelpStep>
                    </ol>
                </div>
                <p className="leading-relaxed">
                    {t('SSO_UI.ENTRA_NOTE')}
                </p>
                <div className="flex flex-col gap-1.5 border-t border-black-100 pt-3">
                    <h3 className="text-xs font-semibold text-black-900">{t('SSO_UI.KEYCLOAK_TITLE')}</h3>
                    <p className="leading-relaxed">
                        <Trans i18nKey="SSO_UI.KEYCLOAK_BODY" values={{ uri: sp.oidcRedirectUri }} components={v} />
                    </p>
                </div>
            </div>
        </details>
    );
}

function PolicySection({ overview, workspaceId }: { overview: SsoOverviewDto; workspaceId: string }) {
    const { t } = useTranslation();
    const locale = useIntlLocale();
    const { toast } = useToast();
    const [update, { isLoading }] = useUpdateSsoSettingsMutation();
    const [revokeSessions, setRevokeSessions] = useState(true);
    const { settings, connections, domains, canManage } = overview;
    const enabled = connections.find((c) => c.status === 'enabled');
    const canRequire = !!enabled && enabled.tested && domains.length > 0;
    const domainList = domains.join(', ');

    const save = async (body: { ssoRequired?: boolean; defaultRole?: string; revokeSessions?: boolean }) => {
        const response: any = await update({ workspace_id: workspaceId, body });
        if (response.error) {
            toast({ description: errorMessage(response.error, t('SSO_UI.SAVE_FAILED')), variant: 'destructive' });
            return;
        }
        if (body.ssoRequired === true) {
            const revoked = response.data?.revokedSessions;
            toast({ description: revoked ? t('SSO_UI.REQUIRED_NOW', { count: revoked }) : t('SSO_UI.REQUIRED_NOW_PLAIN') });
        } else if (body.ssoRequired === false) {
            toast({ description: t('SSO_UI.NO_LONGER_REQUIRED') });
        } else {
            toast({ description: t('SSO_UI.SAVED') });
        }
    };

    return (
        <Section title={t('SSO_UI.POLICY')}>
            <div className="flex flex-col gap-4 rounded border border-black-300 bg-white p-4">
                <label className="flex flex-col gap-1 text-xs font-medium text-black-800">
                    {t('SSO_UI.DEFAULT_ROLE')}
                    <select className={cn(inputClass, 'sm:max-w-[240px]')} value={settings.defaultRole} disabled={isLoading || !canManage} onChange={(e) => save({ defaultRole: e.target.value })}>
                        {settings.assignableRoles.map((role) => (
                            <option key={role} value={role}>
                                {roleLabel(role, t)}
                            </option>
                        ))}
                    </select>
                    <span className="font-normal text-black-600">{t('SSO_UI.DEFAULT_ROLE_HINT')}</span>
                </label>

                <div className="flex flex-col gap-2 border-t border-black-100 pt-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex flex-col gap-1">
                            <span className="text-sm font-semibold text-black-900">{domainList ? t('SSO_UI.REQUIRE_FOR', { domains: domainList }) : t('SSO_UI.REQUIRE')}</span>
                            <span className="max-w-[60ch] text-xs leading-relaxed text-black-600">
                                {t('SSO_UI.REQUIRE_HINT')}
                            </span>
                        </div>
                        {!canManage ? null : settings.ssoRequired ? (
                            <Button size="sm" variant="v2Button" isLoading={isLoading} onClick={() => save({ ssoRequired: false })}>
                                {t('SSO_UI.STOP_REQUIRING')}
                            </Button>
                        ) : (
                            <Button size="sm" variant="primary" isLoading={isLoading} disabled={!canRequire} onClick={() => save({ ssoRequired: true, revokeSessions })}>
                                {t('SSO_UI.REQUIRE')}
                            </Button>
                        )}
                    </div>
                    {settings.ssoRequired ? (
                        <p className="flex items-center gap-2 text-xs text-success-700">
                            <CircleCheck className="h-4 w-4" /> {t('SSO_UI.REQUIRED_SINCE', { time: formatTime(settings.ssoRequiredChangedAt, locale) })}
                        </p>
                    ) : !canManage ? (
                        <p className="text-xs text-black-600">{t('SSO_UI.NOT_REQUIRED')}</p>
                    ) : canRequire ? (
                        <label className="flex items-start gap-2 text-xs text-black-700">
                            <input type="checkbox" className="mt-0.5" checked={revokeSessions} onChange={(e) => setRevokeSessions(e.target.checked)} />
                            {t('SSO_UI.REVOKE_NOW')}
                        </label>
                    ) : (
                        <p className="text-xs text-black-600">{t('SSO_UI.REQUIRE_PRECONDITION')}</p>
                    )}
                    <div className="mt-1 flex items-start gap-2 rounded-md border border-[#D6E2F5] bg-[#F3F7FD] p-3 text-xs leading-relaxed text-black-700">
                        <LifeBuoy className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />
                        <span>
                            <Trans i18nKey="SSO_UI.BREAK_GLASS" components={{ 1: <strong /> }} />
                        </span>
                    </div>
                </div>
            </div>
        </Section>
    );
}

/**
 * Single sign-on settings (docs/sso.md): the service-provider values to enter
 * at the identity provider, the workspace's connections (SAML or OIDC through
 * Polis), testing them, and the SSO-required policy. Owner and admins only.
 */
export default function WorkspaceSsoSection() {
    const workspace = useAppSelector(selectWorkspace);
    const workspaceId: string = workspace?.id;
    const searchParams = useSearchParams();
    const testResult = searchParams?.get('sso_test');
    const { data: overview, isLoading, isError, refetch } = useGetWorkspaceSsoQuery(workspaceId, { skip: !workspaceId });
    const [adding, setAdding] = useState(false);
    const { t } = useTranslation();
    const locale = useIntlLocale();

    if (isLoading) return <p className="text-xs text-black-600">{t('SSO_UI.LOADING')}</p>;
    if (isError || !overview) {
        return (
            <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-[#F3D1D1] bg-[#FBEFEF] px-3 py-3 text-xs text-[#C43D3D]">
                <span>{t('SSO_UI.LOAD_FAILED')}</span>
                <Button size="sm" variant="v2Button" onClick={() => refetch()}>
                    {t('SSO_UI.TRY_AGAIN')}
                </Button>
            </div>
        );
    }
    if (!overview.available) {
        // switched on but incomplete: say so, without pointing at SSO_ENABLED
        const message = overview.reason === 'not_configured' ? sso.NOT_CONFIGURED : sso.NOT_ENABLED;
        return (
            <p className="rounded-md border border-dashed border-black-300 px-3 py-4 text-xs text-black-600" data-testid="sso-unavailable" data-reason={overview.reason === 'not_configured' ? 'not_configured' : 'disabled'}>
                {t(message)}
                {overview.reason === 'not_configured' && <SsoSelfHostingGuide />}
            </p>
        );
    }

    const sp = overview.serviceProvider;
    const ok = testResult === 'ok';
    // the connection this failed test result belongs to: the latest one that failed with it
    const testedConnection = testResult && !ok ? overview.connections.filter((c) => c.lastTestError === testResult).sort((a, b) => (b.lastTestAt ?? '').localeCompare(a.lastTestAt ?? ''))[0] : undefined;

    return (
        <div className="flex flex-col gap-8">
            {!overview.canManage && (
                <div role="note" className="flex items-start gap-2 rounded-md border border-[#D6E2F5] bg-[#F3F7FD] p-3 text-xs leading-relaxed text-black-700">
                    <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />
                    <span>{t('SSO_UI.OWNERS_ONLY')}</span>
                </div>
            )}
            {testResult && (
                <div role="status" className={cn('flex items-start gap-2 rounded-md border p-3 text-xs leading-relaxed', ok ? 'border-[#BFE5D2] bg-[#E7F6EE] text-[#0B6B4A]' : 'border-[#F3D1D1] bg-[#FBEFEF] text-[#9E2F2F]')}>
                    {ok ? <CircleCheck className="mt-0.5 h-4 w-4 shrink-0" /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />}
                    <span className="flex flex-col gap-1">
                        <span>{ssoTestMessage(testResult, t)}</span>
                        {testedConnection && <TestDiagnostics connection={testedConnection} domains={overview.domains} />}
                    </span>
                </div>
            )}

            <Section title={t('SSO_UI.DOMAINS')} description={t('SSO_UI.DOMAINS_DESC')}>
                {overview.domains.length ? (
                    <ul className="flex flex-wrap gap-2">
                        {overview.domains.map((domain) => (
                            <li key={domain} className="flex items-center gap-1.5 rounded-md border border-black-300 bg-white px-2.5 py-1 text-xs font-medium text-black-800">
                                <ShieldCheck className="h-3.5 w-3.5 text-success" />
                                {domain}
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="rounded-md border border-dashed border-black-300 px-3 py-3 text-xs text-black-600">
                        {t('SSO_UI.NO_DOMAIN')} <DomainsLink workspaceName={workspace?.workspaceName} /> {t('SSO_UI.FIRST')}
                    </p>
                )}
            </Section>

            {sp && (
                <Section title={t('SSO_UI.IDP_DETAILS')} description={t('SSO_UI.IDP_DETAILS_DESC')}>
                    <div className="bg-black-50 grid gap-3 rounded-md p-3 md:grid-cols-2">
                        <CopyField label={t('SSO_UI.SAML_ACS')} value={sp.acsUrl} />
                        <CopyField label={t('SSO_UI.SAML_ENTITY')} value={sp.entityId} />
                        <CopyField label={t('SSO_UI.SAML_METADATA')} value={sp.spMetadataUrl} hint={t('SSO_UI.SAML_METADATA_HINT')} />
                        <CopyField label={t('SSO_UI.OIDC_REDIRECT')} value={sp.oidcRedirectUri} />
                    </div>
                    <p className="text-[11px] text-black-600">{t('SSO_UI.EMAIL_NOTE')}</p>
                    <EntraSetupHelp sp={sp} />
                </Section>
            )}

            <Section title={t('SSO_UI.CONNECTIONS')} description={t('SSO_UI.CONNECTIONS_DESC')}>
                {overview.connections.length > 0 && (
                    <ul className="flex flex-col gap-3">
                        {overview.connections.map((connection) => (
                            <ConnectionCard key={connection.id} connection={connection} workspaceId={workspaceId} ssoRequired={overview.settings.ssoRequired} canManage={overview.canManage} domains={overview.domains} />
                        ))}
                    </ul>
                )}
                {!overview.canManage ? null : overview.domains.length === 0 ? (
                    <p className="rounded-md border border-dashed border-black-300 px-3 py-3 text-xs text-black-600">
                        <Trans i18nKey="SSO_UI.NEEDS_DOMAIN" components={{ 1: <DomainsLink workspaceName={workspace?.workspaceName} /> }} />
                    </p>
                ) : adding ? (
                    <AddConnectionForm workspaceId={workspaceId} workspaceName={workspace?.workspaceName} onDone={() => setAdding(false)} />
                ) : overview.connections.length < overview.maxConnections ? (
                    <div>
                        <Button size="sm" variant={overview.connections.length ? 'v2Button' : 'primary'} onClick={() => setAdding(true)}>
                            {t('SSO_UI.ADD')}
                        </Button>
                    </div>
                ) : null}
            </Section>

            <PolicySection overview={overview} workspaceId={workspaceId} />
        </div>
    );
}
