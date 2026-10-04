'use client';

import { FormEvent, useState } from 'react';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

import { AlertTriangle, Check, CircleCheck, Copy, KeyRound, LifeBuoy, ShieldCheck } from 'lucide-react';

import environments from '@app/configs/environments';
import { navigateWithReferrer, ssoTestMessage } from '@app/lib/sso';
import { SsoConnectionDto, SsoConnectionType, SsoOverviewDto } from '@app/models/dtos/workspace-sso-dto';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { useAppSelector } from '@app/store/hooks';
import { useCreateSsoConnectionMutation, useDeleteSsoConnectionMutation, useGetWorkspaceSsoQuery, useSetSsoConnectionEnabledMutation, useUpdateSsoSettingsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

const inputClass = 'h-10 w-full rounded-md border border-black-300 bg-white px-3.5 py-0 text-sm text-black-900 outline-none transition duration-150 placeholder:text-black-400 focus:border-brand-500 focus:shadow-[0_0_0_3px_rgba(36,86,204,0.15)]';

const ROLE_LABELS: Record<string, string> = {
    COLLABORATOR: 'Collaborator',
    VIEWER: 'Viewer',
    EDITOR: 'Editor',
    REVIEWER: 'Reviewer',
    PRIVACY_OFFICER: 'Privacy officer'
};

function errorMessage(error: any, fallback: string): string {
    const data = error?.data;
    if (data && typeof data === 'object' && typeof data.message === 'string') return data.message;
    if (typeof data === 'string') return data;
    return fallback;
}

function formatTime(value?: string | null): string {
    return value ? new Date(value).toLocaleString() : '';
}

function CopyField({ label, value, hint }: { label: string; value: string; hint?: string }) {
    const [copied, setCopied] = useState(false);
    return (
        <div className="flex flex-col gap-1">
            <span className="text-[11px] font-medium uppercase tracking-wide text-black-500">{label}</span>
            <div className="flex items-center justify-between gap-3 rounded-md border border-black-200 bg-white px-3 py-2">
                <code className="break-all text-[13px] text-black-800">{value}</code>
                <button
                    type="button"
                    aria-label={`Copy ${label}`}
                    onClick={async () => {
                        try {
                            await navigator.clipboard.writeText(value);
                            setCopied(true);
                            setTimeout(() => setCopied(false), 1500);
                        } catch {
                            setCopied(false);
                        }
                    }}
                    className="shrink-0 rounded p-1 text-black-500 transition-colors hover:text-black-800"
                >
                    {copied ? <Check className="h-4 w-4 text-[#0E8A5F]" /> : <Copy className="h-4 w-4" />}
                    <span className="sr-only" aria-live="polite">
                        {copied ? 'Copied' : ''}
                    </span>
                </button>
            </div>
            {hint && <span className="text-[11px] text-black-500">{hint}</span>}
        </div>
    );
}

function Section({ title, description, children }: { title: string; description?: React.ReactNode; children: React.ReactNode }) {
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

function ConnectionCard({ connection, workspaceId, ssoRequired, canManage }: { connection: SsoConnectionDto; workspaceId: string; ssoRequired: boolean; canManage: boolean }) {
    const { toast } = useToast();
    const [setEnabled, { isLoading: isToggling }] = useSetSsoConnectionEnabledMutation();
    const [deleteConnection, { isLoading: isDeleting }] = useDeleteSsoConnectionMutation();
    const enabled = connection.status === 'enabled';
    const locked = enabled && ssoRequired;

    const toggle = async () => {
        const response: any = await setEnabled({ workspace_id: workspaceId, connection_id: connection.id, enabled: !enabled });
        if (response.error) toast({ description: errorMessage(response.error, 'Could not change the connection.'), variant: 'destructive' });
    };

    const remove = async () => {
        if (!window.confirm(`Delete “${connection.name}”? Members can no longer sign in with it.`)) return;
        const response: any = await deleteConnection({ workspace_id: workspaceId, connection_id: connection.id });
        if (response.error) toast({ description: errorMessage(response.error, 'Could not delete the connection.'), variant: 'destructive' });
        else toast({ description: `Deleted ${connection.name}.` });
    };

    const test = () => navigateWithReferrer(`${environments.API_ENDPOINT_HOST}/workspaces/${workspaceId}/sso/connections/${connection.id}/test`);

    return (
        <li className="flex flex-col gap-3 rounded-lg border border-black-200 bg-white p-4" data-testid={`sso-connection-${connection.id}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 flex-col gap-1">
                    <div className="flex flex-wrap items-center gap-2">
                        <KeyRound className={cn('h-4 w-4 shrink-0', enabled ? 'text-[#0E8A5F]' : 'text-black-500')} />
                        <span className="break-all text-sm font-semibold text-black-900">{connection.name}</span>
                        <span className="rounded bg-black-100 px-1.5 py-0.5 text-[11px] font-medium uppercase text-black-600">{connection.type}</span>
                        <span className={cn('rounded px-1.5 py-0.5 text-[11px] font-medium', enabled ? 'bg-[#E7F6EE] text-[#0E8A5F]' : 'bg-black-100 text-black-600')}>{enabled ? 'Enabled' : 'Disabled'}</span>
                        {connection.tested ? (
                            <span className="rounded bg-[#E7F6EE] px-1.5 py-0.5 text-[11px] font-medium text-[#0E8A5F]">Tested</span>
                        ) : (
                            <span className="rounded bg-[#FDF3E3] px-1.5 py-0.5 text-[11px] font-medium text-[#9A5B00]">Not tested</span>
                        )}
                    </div>
                    <span className="break-all text-xs text-black-500">
                        {connection.idpEntityId || connection.oidcDiscoveryUrl || connection.metadataUrl || ''}
                        {connection.oidcClientId ? ` · client ${connection.oidcClientId}` : ''}
                    </span>
                    <span className="text-xs text-black-500">{connection.testedAt ? `Last successful test ${formatTime(connection.testedAt)}` : 'Test it before you require single sign-on.'}</span>
                    {connection.lastTestError && <span className="text-xs text-[#C43D3D]">Last test failed: {ssoTestMessage(connection.lastTestError)}</span>}
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                    <Button size="sm" variant="v2Button" onClick={test}>
                        Test connection
                    </Button>
                    {canManage && (
                        <>
                            <Button
                                size="sm"
                                variant={enabled ? 'v2Button' : 'primary'}
                                isLoading={isToggling}
                                disabled={locked || (!enabled && !connection.tested)}
                                onClick={toggle}
                                title={locked ? 'Turn off “Require single sign-on” first' : !enabled && !connection.tested ? 'Test the connection successfully first' : undefined}
                            >
                                {enabled ? 'Disable' : 'Enable'}
                            </Button>
                            <Button size="sm" variant="dangerGhost" isLoading={isDeleting} disabled={locked} onClick={remove} aria-label={`Delete ${connection.name}`}>
                                Delete
                            </Button>
                        </>
                    )}
                </div>
            </div>
        </li>
    );
}

function DomainsLink({ workspaceName }: { workspaceName?: string }) {
    return (
        <Link className="text-brand-500 underline" href={`/${workspaceName}/dashboard/domains`}>
            Verify your organisation&apos;s domain
        </Link>
    );
}

function AddConnectionForm({ workspaceId, workspaceName, onDone }: { workspaceId: string; workspaceName?: string; onDone: () => void }) {
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
            setError(errorMessage(response.error, 'Could not create the connection.'));
            setNeedsDomain(response.error?.data?.code === 'sso_domain_required');
            return;
        }
        setClientSecret('');
        toast({ description: 'Connection created. Test it, then enable it.' });
        onDone();
    };

    return (
        <form onSubmit={submit} className="flex flex-col gap-4 rounded-lg border border-black-200 bg-white p-4" noValidate>
            <fieldset className="flex flex-wrap gap-4">
                <legend className="mb-2 text-xs font-semibold text-black-800">Protocol</legend>
                {(['saml', 'oidc'] as SsoConnectionType[]).map((value) => (
                    <label key={value} className="flex items-center gap-2 text-sm text-black-800">
                        <input type="radio" name="sso-type" value={value} checked={type === value} onChange={() => setType(value)} />
                        {value === 'saml' ? 'SAML 2.0' : 'OpenID Connect'}
                    </label>
                ))}
            </fieldset>
            <label className="flex flex-col gap-1 text-xs font-medium text-black-800">
                Name (optional)
                <input className={inputClass} value={name} maxLength={100} placeholder={type === 'saml' ? 'Okta' : 'Microsoft Entra ID'} onChange={(e) => setName(e.target.value)} />
            </label>
            {type === 'saml' ? (
                <>
                    <fieldset className="flex flex-wrap gap-4">
                        <legend className="mb-2 text-xs font-semibold text-black-800">Identity provider metadata</legend>
                        <label className="flex items-center gap-2 text-sm text-black-800">
                            <input type="radio" name="sso-source" checked={source === 'url'} onChange={() => setSource('url')} />
                            Metadata URL
                        </label>
                        <label className="flex items-center gap-2 text-sm text-black-800">
                            <input type="radio" name="sso-source" checked={source === 'xml'} onChange={() => setSource('xml')} />
                            Paste metadata XML
                        </label>
                    </fieldset>
                    {source === 'url' ? (
                        <label className="flex flex-col gap-1 text-xs font-medium text-black-800">
                            Metadata URL
                            <input className={inputClass} type="url" value={metadataUrl} placeholder="https://idp.example.com/app/metadata" onChange={(e) => setMetadataUrl(e.target.value)} />
                            <span className="font-normal text-black-500">Must be https and on the public internet.</span>
                        </label>
                    ) : (
                        <label className="flex flex-col gap-1 text-xs font-medium text-black-800">
                            Metadata XML
                            <textarea className={cn(inputClass, 'h-40 py-2 font-mono text-xs')} value={metadataXml} placeholder="<md:EntityDescriptor …>" onChange={(e) => setMetadataXml(e.target.value)} spellCheck={false} />
                        </label>
                    )}
                </>
            ) : (
                <>
                    <label className="flex flex-col gap-1 text-xs font-medium text-black-800">
                        Discovery URL
                        <input className={inputClass} type="url" value={discoveryUrl} placeholder="https://login.example.com/.well-known/openid-configuration" onChange={(e) => setDiscoveryUrl(e.target.value)} />
                    </label>
                    <label className="flex flex-col gap-1 text-xs font-medium text-black-800">
                        Client ID
                        <input className={inputClass} value={clientId} autoComplete="off" onChange={(e) => setClientId(e.target.value)} />
                    </label>
                    <label className="flex flex-col gap-1 text-xs font-medium text-black-800">
                        Client secret
                        <input className={inputClass} type="password" value={clientSecret} autoComplete="new-password" onChange={(e) => setClientSecret(e.target.value)} />
                        <span className="font-normal text-black-500">Stored by the single sign-on service only; it is never shown again.</span>
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
                    Create connection
                </Button>
                <Button type="button" size="sm" variant="v2Button" onClick={onDone}>
                    Cancel
                </Button>
            </div>
        </form>
    );
}

function PolicySection({ overview, workspaceId }: { overview: SsoOverviewDto; workspaceId: string }) {
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
            toast({ description: errorMessage(response.error, 'Could not save the setting.'), variant: 'destructive' });
            return;
        }
        if (body.ssoRequired === true) {
            const revoked = response.data?.revokedSessions;
            toast({ description: revoked ? `Single sign-on is now required. ${revoked} session${revoked === 1 ? ' was' : 's were'} signed out.` : 'Single sign-on is now required.' });
        } else if (body.ssoRequired === false) {
            toast({ description: 'Single sign-on is no longer required.' });
        } else {
            toast({ description: 'Saved.' });
        }
    };

    return (
        <Section title="Policy">
            <div className="flex flex-col gap-4 rounded-lg border border-black-200 bg-white p-4">
                <label className="flex flex-col gap-1 text-xs font-medium text-black-800">
                    Role for new members
                    <select className={cn(inputClass, 'sm:max-w-[240px]')} value={settings.defaultRole} disabled={isLoading || !canManage} onChange={(e) => save({ defaultRole: e.target.value })}>
                        {settings.assignableRoles.map((role) => (
                            <option key={role} value={role}>
                                {ROLE_LABELS[role] ?? role}
                            </option>
                        ))}
                    </select>
                    <span className="font-normal text-black-500">Someone signing in with single sign-on for the first time joins this workspace with this role. Existing members keep theirs.</span>
                </label>

                <div className="flex flex-col gap-2 border-t border-black-100 pt-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex flex-col gap-1">
                            <span className="text-sm font-semibold text-black-900">Require single sign-on{domainList ? ` for ${domainList}` : ''}</span>
                            <span className="max-w-[60ch] text-xs leading-relaxed text-black-600">
                                Addresses on these domains can then only sign in through your identity provider: sign-in codes by email and Google are refused, here and on every workspace.
                            </span>
                        </div>
                        {!canManage ? null : settings.ssoRequired ? (
                            <Button size="sm" variant="v2Button" isLoading={isLoading} onClick={() => save({ ssoRequired: false })}>
                                Stop requiring
                            </Button>
                        ) : (
                            <Button size="sm" variant="primary" isLoading={isLoading} disabled={!canRequire} onClick={() => save({ ssoRequired: true, revokeSessions })}>
                                Require single sign-on
                            </Button>
                        )}
                    </div>
                    {settings.ssoRequired ? (
                        <p className="flex items-center gap-2 text-xs text-[#0E8A5F]">
                            <CircleCheck className="h-4 w-4" /> Required since {formatTime(settings.ssoRequiredChangedAt)}.
                        </p>
                    ) : !canManage ? (
                        <p className="text-xs text-black-500">Not required.</p>
                    ) : canRequire ? (
                        <label className="flex items-start gap-2 text-xs text-black-700">
                            <input type="checkbox" className="mt-0.5" checked={revokeSessions} onChange={(e) => setRevokeSessions(e.target.checked)} />
                            Also sign out members on these domains now, so their next sign-in goes through your identity provider (your own session stays).
                        </label>
                    ) : (
                        <p className="text-xs text-black-500">Verify a domain, enable a connection and test it successfully first.</p>
                    )}
                    <div className="mt-1 flex items-start gap-2 rounded-md border border-[#D6E2F5] bg-[#F3F7FD] p-3 text-xs leading-relaxed text-black-700">
                        <LifeBuoy className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />
                        <span>
                            <strong>Break-glass:</strong> the workspace owner can always sign in with a code sent by email, even when single sign-on is required, so a broken identity provider can&apos;t lock everyone out. Keep the owner&apos;s mailbox
                            safe.
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

    if (isLoading) return <p className="text-xs text-black-500">Loading…</p>;
    if (isError || !overview) {
        return (
            <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-[#F3D1D1] bg-[#FBEFEF] px-3 py-3 text-xs text-[#C43D3D]">
                <span>Single sign-on settings couldn&apos;t be loaded.</span>
                <Button size="sm" variant="v2Button" onClick={() => refetch()}>
                    Try again
                </Button>
            </div>
        );
    }
    if (!overview.available) {
        return <p className="rounded-md border border-dashed border-black-200 px-3 py-4 text-xs text-black-600">Single sign-on is not enabled on this instance. The operator turns it on (SSO_ENABLED, see docs/sso.md).</p>;
    }

    const sp = overview.serviceProvider;
    const ok = testResult === 'ok';

    return (
        <div className="flex flex-col gap-8">
            {!overview.canManage && (
                <div role="note" className="flex items-start gap-2 rounded-md border border-[#D6E2F5] bg-[#F3F7FD] p-3 text-xs leading-relaxed text-black-700">
                    <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />
                    <span>Only the workspace owner can change single sign-on: a connection decides who every address on your verified domains is, the owner&apos;s included. You can view the settings and test a connection.</span>
                </div>
            )}
            {testResult && (
                <div role="status" className={cn('flex items-start gap-2 rounded-md border p-3 text-xs leading-relaxed', ok ? 'border-[#BFE5D2] bg-[#E7F6EE] text-[#0B6B4A]' : 'border-[#F3D1D1] bg-[#FBEFEF] text-[#9E2F2F]')}>
                    {ok ? <CircleCheck className="mt-0.5 h-4 w-4 shrink-0" /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />}
                    <span>{ssoTestMessage(testResult)}</span>
                </div>
            )}

            <Section title="Domains" description="Single sign-on applies to your verified email domains only. Someone your identity provider signs in with an address on another domain is refused.">
                {overview.domains.length ? (
                    <ul className="flex flex-wrap gap-2">
                        {overview.domains.map((domain) => (
                            <li key={domain} className="flex items-center gap-1.5 rounded-md border border-black-200 bg-white px-2.5 py-1 text-xs font-medium text-black-800">
                                <ShieldCheck className="h-3.5 w-3.5 text-[#0E8A5F]" />
                                {domain}
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="rounded-md border border-dashed border-black-200 px-3 py-3 text-xs text-black-600">
                        No verified domain yet.{' '}
                        <Link className="text-brand-500 underline" href={`/${workspace?.workspaceName}/dashboard/domains`}>
                            Verify your organisation&apos;s domain
                        </Link>{' '}
                        first.
                    </p>
                )}
            </Section>

            {sp && (
                <Section title="Details for your identity provider" description="Enter these when you register BetterCollected as an application at your identity provider.">
                    <div className="bg-black-50 grid gap-3 rounded-md p-3 md:grid-cols-2">
                        <CopyField label="SAML ACS URL (reply URL)" value={sp.acsUrl} />
                        <CopyField label="SAML entity ID (audience)" value={sp.entityId} />
                        <CopyField label="SAML SP metadata" value={sp.spMetadataUrl} hint="Some identity providers can read the two values above from this." />
                        <CopyField label="OIDC redirect URI" value={sp.oidcRedirectUri} />
                    </div>
                    <p className="text-[11px] text-black-500">Your identity provider must send the user&apos;s email address (SAML: the NameID or an email attribute; OIDC: the email claim).</p>
                </Section>
            )}

            <Section title="Connections" description="One connection signs members in at a time: enabling one disables the others. A connection can only be enabled after a successful test.">
                {overview.connections.length > 0 && (
                    <ul className="flex flex-col gap-3">
                        {overview.connections.map((connection) => (
                            <ConnectionCard key={connection.id} connection={connection} workspaceId={workspaceId} ssoRequired={overview.settings.ssoRequired} canManage={overview.canManage} />
                        ))}
                    </ul>
                )}
                {!overview.canManage ? null : overview.domains.length === 0 ? (
                    <p className="rounded-md border border-dashed border-black-200 px-3 py-3 text-xs text-black-600">
                        A connection needs a verified email domain. <DomainsLink workspaceName={workspace?.workspaceName} /> first.
                    </p>
                ) : adding ? (
                    <AddConnectionForm workspaceId={workspaceId} workspaceName={workspace?.workspaceName} onDone={() => setAdding(false)} />
                ) : overview.connections.length < overview.maxConnections ? (
                    <div>
                        <Button size="sm" variant={overview.connections.length ? 'v2Button' : 'primary'} onClick={() => setAdding(true)}>
                            Add connection
                        </Button>
                    </div>
                ) : null}
            </Section>

            <PolicySection overview={overview} workspaceId={workspaceId} />
        </div>
    );
}
