'use client';

import { FormEvent, useState } from 'react';

import { AlertTriangle, Check, Copy, Globe2, ShieldCheck } from 'lucide-react';
import { Trans, useTranslation } from 'react-i18next';

import { useIntlLocale } from '@app/lib/hooks/use-intl-locale';

import { WorkspaceDomainDto, WorkspaceDomainStatus } from '@app/models/dtos/workspace-domain-dto';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { useAppSelector } from '@app/store/hooks';
import { useClaimEmailDomainMutation, useDeleteEmailDomainMutation, useGetEmailDomainsQuery, useVerifyEmailDomainMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

const RECORD_HOST = '_bettercollected-verification';

const STATUS: Record<WorkspaceDomainStatus, { label: string; className: string }> = {
    pending: { label: 'DOMAINS_UI.STATUS_PENDING', className: 'bg-black-100 text-black-600' },
    verified: { label: 'DOMAINS_UI.STATUS_VERIFIED', className: 'bg-[#E7F6EE] text-success-700' },
    failed: { label: 'DOMAINS_UI.STATUS_FAILED', className: 'bg-[#FBEFEF] text-[#C43D3D]' },
    conflict: { label: 'DOMAINS_UI.STATUS_CONFLICT', className: 'bg-[#FDF3E3] text-[#9A5B00]' }
};

const KNOWN_CHECK_ERRORS = ['no_record', 'token_mismatch', 'dns_timeout', 'dns_error', 'verified_by_another_workspace'];

/** Why the last check did not succeed, in the dashboard's language. */
export function checkErrorMessage(domain: WorkspaceDomainDto, t: (key: string, options?: Record<string, string>) => string): string | null {
    if (domain.lastCheckError === null || domain.lastCheckError === undefined) return null;
    const known = KNOWN_CHECK_ERRORS.includes(domain.lastCheckError) ? domain.lastCheckError : 'default';
    return t(`DOMAINS_UI.ERR_${known}`, { name: domain.txtRecordName });
}

function errorMessage(error: any, fallback: string): string {
    const data = error?.data;
    if (data && typeof data === 'object' && typeof data.message === 'string') return data.message;
    if (typeof data === 'string') return data;
    return fallback;
}

function CopyButton({ value, label }: { value: string; label: string }) {
    const { t } = useTranslation();
    const [copied, setCopied] = useState(false);
    return (
        <button
            type="button"
            aria-label={label}
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
                {copied ? t('STAFF.COMMON.COPIED') : ''}
            </span>
        </button>
    );
}

function RecordField({ label, value, copyLabel }: { label: string; value: string; copyLabel: string }) {
    return (
        <div className="flex flex-col gap-1">
            <span className="text-[11px] font-medium uppercase tracking-wide text-black-600">{label}</span>
            <div className="flex items-center justify-between gap-3 rounded-md border border-black-300 bg-white px-3 py-2">
                <code className="break-all text-[13px] text-black-800">{value}</code>
                <CopyButton value={value} label={copyLabel} />
            </div>
        </div>
    );
}

function formatTime(value: string | null | undefined, locale: string): string {
    return value ? new Date(value).toLocaleString(locale) : '';
}

function DomainCard({ domain, workspaceId }: { domain: WorkspaceDomainDto; workspaceId: string }) {
    const { t } = useTranslation();
    const locale = useIntlLocale();
    const { toast } = useToast();
    const [verifyDomain, { isLoading: isVerifying }] = useVerifyEmailDomainMutation();
    const [deleteDomain, { isLoading: isDeleting }] = useDeleteEmailDomainMutation();
    const status = STATUS[domain.status] ?? STATUS.pending;
    const verified = domain.status === 'verified';
    const problem = checkErrorMessage(domain, t);

    const handleVerify = async () => {
        const response: any = await verifyDomain({ workspace_id: workspaceId, domain_id: domain.id });
        if (response.error) {
            toast({ description: errorMessage(response.error, t('DOMAINS_UI.CHECK_FAILED')), variant: 'destructive' });
            return;
        }
        const result: WorkspaceDomainDto = response.data;
        if (result.status === 'verified' && !result.lastCheckError) {
            toast({ description: t('DOMAINS_UI.VERIFIED_TOAST', { domain: result.displayDomain }) });
        } else {
            toast({ description: checkErrorMessage(result, t) ?? t('DOMAINS_UI.NOT_VERIFIED'), variant: 'destructive' });
        }
    };

    const handleDelete = async () => {
        const consequence = verified ? t('DOMAINS_UI.REMOVE_CONSEQUENCE') : '';
        if (!window.confirm(t('DOMAINS_UI.REMOVE_CONFIRM', { domain: domain.displayDomain, consequence }))) return;
        const response: any = await deleteDomain({ workspace_id: workspaceId, domain_id: domain.id });
        if (response.error) {
            toast({ description: errorMessage(response.error, t('DOMAINS_UI.REMOVE_FAILED')), variant: 'destructive' });
        } else {
            toast({ description: t('DOMAINS_UI.REMOVED', { domain: domain.displayDomain }) });
        }
    };

    return (
        <li className="flex flex-col gap-4 rounded border border-black-300 bg-white p-4" data-testid={`domain-${domain.domain}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 flex-col gap-1" aria-live="polite">
                    <div className="flex flex-wrap items-center gap-2">
                        {verified ? <ShieldCheck className="h-4 w-4 shrink-0 text-success" /> : <Globe2 className="h-4 w-4 shrink-0 text-black-600" />}
                        <span className="break-all text-sm font-semibold text-black-900">{domain.displayDomain}</span>
                        <span className={cn('rounded px-1.5 py-0.5 text-[11px] font-medium', status.className)}>{t(status.label)}</span>
                    </div>
                    {domain.displayDomain !== domain.domain && <span className="break-all text-xs text-black-600">{domain.domain}</span>}
                    <span className="text-xs text-black-600">
                        {verified && domain.verifiedAt ? t('DOMAINS_UI.VERIFIED_AT', { time: formatTime(domain.verifiedAt, locale) }) : t('DOMAINS_UI.ADD_RECORD_THEN_CHECK')}
                        {domain.lastCheckedAt ? ` · ${t('DOMAINS_UI.LAST_CHECKED', { time: formatTime(domain.lastCheckedAt, locale) })}` : ''}
                    </span>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                    {domain.status !== 'conflict' && (
                        <Button size="sm" variant={verified ? 'v2Button' : 'primary'} isLoading={isVerifying} onClick={handleVerify}>
                            {verified ? t('DOMAINS_UI.CHECK_AGAIN') : t('DOMAINS_UI.VERIFY_NOW')}
                        </Button>
                    )}
                    <Button size="sm" variant="dangerGhost" isLoading={isDeleting} onClick={handleDelete} aria-label={t('DOMAINS_UI.REMOVE_ARIA', { domain: domain.displayDomain })}>
                        {t('DOMAINS_UI.REMOVE')}
                    </Button>
                </div>
            </div>

            {domain.verificationLostAt && (
                <div role="alert" className="flex items-start gap-2 rounded-md border border-[#F0D9B5] bg-[#FDF8EF] p-3 text-xs text-black-700">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#9A5B00]" />
                    <span>{t('DOMAINS_UI.LOST', { time: formatTime(domain.verificationLostAt, locale) })}</span>
                </div>
            )}

            <div aria-live="polite">{problem && !domain.verificationLostAt && <p className={cn('text-xs', verified ? 'text-black-600' : 'text-[#C43D3D]')}>{problem}</p>}</div>

            {domain.status !== 'conflict' && (
                <div className="bg-black-50 flex flex-col gap-3 rounded-md p-3">
                    <p className="text-xs leading-relaxed text-black-700">
                        {verified ? t('DOMAINS_UI.KEEP_RECORD') : t('DOMAINS_UI.ADD_RECORD_HELP')}
                    </p>
                    <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
                        <RecordField label={t('DOMAINS_UI.NAME_HOST')} value={domain.txtRecordName} copyLabel={t('DOMAINS_UI.COPY_NAME', { domain: domain.displayDomain })} />
                        <RecordField label={t('DOMAINS_UI.VALUE')} value={domain.txtRecordValue} copyLabel={t('DOMAINS_UI.COPY_VALUE', { domain: domain.displayDomain })} />
                    </div>
                    {!verified && (
                        <p className="text-[11px] text-black-600">
                            <Trans i18nKey="DOMAINS_UI.TYPE_HOST" values={{ host: RECORD_HOST }} components={{ 1: <code />, 2: <code /> }} />
                        </p>
                    )}
                </div>
            )}
        </li>
    );
}

/**
 * Verified email domains: a workspace proves it owns an email domain with a
 * DNS TXT record. Single sign-on may only use domains verified here
 * (docs/verified-domains.md). Owner and admins only.
 */
export default function WorkspaceDomainsSection() {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const workspaceId: string = workspace?.id;
    const { toast } = useToast();
    const { data: domains = [], isLoading, isError, refetch } = useGetEmailDomainsQuery(workspaceId, { skip: !workspaceId });
    const [claimDomain, { isLoading: isClaiming }] = useClaimEmailDomainMutation();
    const [draft, setDraft] = useState('');
    const [claimError, setClaimError] = useState<string | null>(null);

    const handleClaim = async (event: FormEvent) => {
        event.preventDefault();
        const domain = draft.trim();
        if (!domain) return;
        setClaimError(null);
        const response: any = await claimDomain({ workspace_id: workspaceId, domain });
        if (response.error) {
            setClaimError(errorMessage(response.error, t('DOMAINS_UI.ADD_FAILED')));
        } else {
            setDraft('');
            toast({ description: t('DOMAINS_UI.ADDED', { domain: response.data?.displayDomain ?? domain }) });
        }
    };

    return (
        <div className="flex flex-col gap-6">
            <form onSubmit={handleClaim} className="flex flex-col gap-2" noValidate>
                <label htmlFor="workspace-domain-input" className="text-sm font-semibold text-black-900">
                    {t('DOMAINS_UI.ADD_A_DOMAIN')}
                </label>
                <div className="flex flex-col gap-2 sm:flex-row">
                    <input
                        id="workspace-domain-input"
                        value={draft}
                        maxLength={300}
                        placeholder="acme.com"
                        autoComplete="off"
                        spellCheck={false}
                        aria-invalid={!!claimError}
                        aria-describedby={claimError ? 'workspace-domain-error' : undefined}
                        onChange={(e) => {
                            setDraft(e.target.value);
                            setClaimError(null);
                        }}
                        className="h-10 w-full rounded-md border border-control bg-white px-3.5 text-sm text-black-900 outline-hidden transition duration-150 placeholder:text-black-600 focus:border-brand-500 sm:max-w-[360px]"
                    />
                    <Button type="submit" size="sm" variant="primary" isLoading={isClaiming} disabled={!draft.trim()}>
                        {t('DOMAINS_UI.ADD_DOMAIN')}
                    </Button>
                </div>
                {claimError ? (
                    <p id="workspace-domain-error" role="alert" className="text-xs text-[#C43D3D]">
                        {claimError}
                    </p>
                ) : (
                    <p className="text-xs text-black-600">{t('DOMAINS_UI.ADD_HELP')}</p>
                )}
            </form>

            <div className="flex flex-col gap-3">
                <h2 className="text-sm font-semibold text-black-900">{t('DOMAINS_UI.DOMAINS')}</h2>
                {isLoading ? (
                    <p className="text-xs text-black-600">{t('STAFF.COMMON.LOADING')}</p>
                ) : isError ? (
                    <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-[#F3D1D1] bg-[#FBEFEF] px-3 py-3 text-xs text-[#C43D3D]">
                        <span>{t('DOMAINS_UI.LOAD_FAILED')}</span>
                        <Button size="sm" variant="v2Button" onClick={() => refetch()}>
                            {t('STAFF.COMMON.TRY_AGAIN')}
                        </Button>
                    </div>
                ) : domains.length === 0 ? (
                    <p className="rounded-md border border-dashed border-black-300 px-3 py-4 text-center text-xs text-black-600">{t('DOMAINS_UI.NONE')}</p>
                ) : (
                    <ul className="flex flex-col gap-3">
                        {domains.map((domain) => (
                            <DomainCard key={domain.id} domain={domain} workspaceId={workspaceId} />
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}
