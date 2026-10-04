'use client';

import { FormEvent, useState } from 'react';

import { AlertTriangle, Check, Copy, Globe2, ShieldCheck } from 'lucide-react';

import { WorkspaceDomainDto, WorkspaceDomainStatus } from '@app/models/dtos/workspace-domain-dto';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { useAppSelector } from '@app/store/hooks';
import { useClaimEmailDomainMutation, useDeleteEmailDomainMutation, useGetEmailDomainsQuery, useVerifyEmailDomainMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

const RECORD_HOST = '_bettercollected-verification';

const STATUS: Record<WorkspaceDomainStatus, { label: string; className: string }> = {
    pending: { label: 'Not verified yet', className: 'bg-black-100 text-black-600' },
    verified: { label: 'Verified', className: 'bg-[#E7F6EE] text-[#0E8A5F]' },
    failed: { label: 'Verification failed', className: 'bg-[#FBEFEF] text-[#C43D3D]' },
    conflict: { label: 'Verified by another workspace', className: 'bg-[#FDF3E3] text-[#9A5B00]' }
};

export function checkErrorMessage(domain: WorkspaceDomainDto): string | null {
    switch (domain.lastCheckError) {
        case null:
        case undefined:
            return null;
        case 'no_record':
            return `No TXT record was found at ${domain.txtRecordName}. DNS changes can take a while to show up; try again later.`;
        case 'token_mismatch':
            return 'TXT records exist at that name, but none has this verification value. Check that the value was copied in full.';
        case 'dns_timeout':
            return 'The DNS lookup timed out. Try again in a moment.';
        case 'dns_error':
            return 'The DNS lookup failed. Try again in a moment.';
        case 'verified_by_another_workspace':
            return 'Another workspace has already verified this domain. If your organisation owns it, contact support.';
        default:
            return 'The last check did not succeed.';
    }
}

function errorMessage(error: any, fallback: string): string {
    const data = error?.data;
    if (data && typeof data === 'object' && typeof data.message === 'string') return data.message;
    if (typeof data === 'string') return data;
    return fallback;
}

function CopyButton({ value, label }: { value: string; label: string }) {
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
            className="shrink-0 rounded p-1 text-black-500 transition-colors hover:text-black-800"
        >
            {copied ? <Check className="h-4 w-4 text-[#0E8A5F]" /> : <Copy className="h-4 w-4" />}
            <span className="sr-only" aria-live="polite">
                {copied ? 'Copied' : ''}
            </span>
        </button>
    );
}

function RecordField({ label, value, copyLabel }: { label: string; value: string; copyLabel: string }) {
    return (
        <div className="flex flex-col gap-1">
            <span className="text-[11px] font-medium uppercase tracking-wide text-black-500">{label}</span>
            <div className="flex items-center justify-between gap-3 rounded-md border border-black-200 bg-white px-3 py-2">
                <code className="break-all text-[13px] text-black-800">{value}</code>
                <CopyButton value={value} label={copyLabel} />
            </div>
        </div>
    );
}

function formatTime(value?: string | null): string {
    return value ? new Date(value).toLocaleString() : '';
}

function DomainCard({ domain, workspaceId }: { domain: WorkspaceDomainDto; workspaceId: string }) {
    const { toast } = useToast();
    const [verifyDomain, { isLoading: isVerifying }] = useVerifyEmailDomainMutation();
    const [deleteDomain, { isLoading: isDeleting }] = useDeleteEmailDomainMutation();
    const status = STATUS[domain.status] ?? STATUS.pending;
    const verified = domain.status === 'verified';
    const problem = checkErrorMessage(domain);

    const handleVerify = async () => {
        const response: any = await verifyDomain({ workspace_id: workspaceId, domain_id: domain.id });
        if (response.error) {
            toast({ description: errorMessage(response.error, 'Could not check the domain. Please try again.'), variant: 'destructive' });
            return;
        }
        const result: WorkspaceDomainDto = response.data;
        if (result.status === 'verified' && !result.lastCheckError) {
            toast({ description: `${result.displayDomain} is verified.` });
        } else {
            toast({ description: checkErrorMessage(result) ?? 'Not verified yet.', variant: 'destructive' });
        }
    };

    const handleDelete = async () => {
        const consequence = verified ? ' Single sign-on and anything else relying on it will stop trusting this domain for this workspace.' : '';
        if (!window.confirm(`Remove ${domain.displayDomain}?${consequence}`)) return;
        const response: any = await deleteDomain({ workspace_id: workspaceId, domain_id: domain.id });
        if (response.error) {
            toast({ description: errorMessage(response.error, 'Could not remove the domain. Please try again.'), variant: 'destructive' });
        } else {
            toast({ description: `Removed ${domain.displayDomain}.` });
        }
    };

    return (
        <li className="flex flex-col gap-4 rounded-lg border border-black-200 bg-white p-4" data-testid={`domain-${domain.domain}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 flex-col gap-1" aria-live="polite">
                    <div className="flex flex-wrap items-center gap-2">
                        {verified ? <ShieldCheck className="h-4 w-4 shrink-0 text-[#0E8A5F]" /> : <Globe2 className="h-4 w-4 shrink-0 text-black-500" />}
                        <span className="break-all text-sm font-semibold text-black-900">{domain.displayDomain}</span>
                        <span className={cn('rounded px-1.5 py-0.5 text-[11px] font-medium', status.className)}>{status.label}</span>
                    </div>
                    {domain.displayDomain !== domain.domain && <span className="break-all text-xs text-black-500">{domain.domain}</span>}
                    <span className="text-xs text-black-500">
                        {verified && domain.verifiedAt ? `Verified ${formatTime(domain.verifiedAt)}` : 'Add the TXT record below, then check it.'}
                        {domain.lastCheckedAt ? ` · Last checked ${formatTime(domain.lastCheckedAt)}` : ''}
                    </span>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                    {domain.status !== 'conflict' && (
                        <Button size="sm" variant={verified ? 'v2Button' : 'primary'} isLoading={isVerifying} onClick={handleVerify}>
                            {verified ? 'Check again' : 'Verify now'}
                        </Button>
                    )}
                    <Button size="sm" variant="dangerGhost" isLoading={isDeleting} onClick={handleDelete} aria-label={`Remove ${domain.displayDomain}`}>
                        Remove
                    </Button>
                </div>
            </div>

            {domain.verificationLostAt && (
                <div role="alert" className="flex items-start gap-2 rounded-md border border-[#F0D9B5] bg-[#FDF8EF] p-3 text-xs text-black-700">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#9A5B00]" />
                    <span>The verification record has been missing since {formatTime(domain.verificationLostAt)}. The domain stays verified for this workspace, but please restore the TXT record below.</span>
                </div>
            )}

            <div aria-live="polite">{problem && !domain.verificationLostAt && <p className={cn('text-xs', verified ? 'text-black-600' : 'text-[#C43D3D]')}>{problem}</p>}</div>

            {domain.status !== 'conflict' && (
                <div className="bg-black-50 flex flex-col gap-3 rounded-md p-3">
                    <p className="text-xs leading-relaxed text-black-700">
                        {verified
                            ? 'Keep this TXT record in place: the domain is checked again regularly.'
                            : 'At your DNS provider, add a TXT record with this name and value. Some providers add the domain to the name for you; then enter only the first part. DNS changes can take up to a few hours to show up.'}
                    </p>
                    <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
                        <RecordField label="Name (host)" value={domain.txtRecordName} copyLabel={`Copy record name for ${domain.displayDomain}`} />
                        <RecordField label="Value" value={domain.txtRecordValue} copyLabel={`Copy record value for ${domain.displayDomain}`} />
                    </div>
                    {!verified && (
                        <p className="text-[11px] text-black-500">
                            Type <code>TXT</code> · host only: <code>{RECORD_HOST}</code>
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
            setClaimError(errorMessage(response.error, 'Could not add the domain. Please try again.'));
        } else {
            setDraft('');
            toast({ description: `Added ${response.data?.displayDomain ?? domain}. Now add its TXT record.` });
        }
    };

    return (
        <div className="flex flex-col gap-6">
            <form onSubmit={handleClaim} className="flex flex-col gap-2" noValidate>
                <label htmlFor="workspace-domain-input" className="text-sm font-semibold text-black-900">
                    Add a domain
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
                        className="h-10 w-full rounded-md border border-black-300 bg-white px-3.5 text-sm text-black-900 outline-none transition duration-150 placeholder:text-black-400 focus:border-brand-500 focus:shadow-[0_0_0_3px_rgba(36,86,204,0.15)] sm:max-w-[360px]"
                    />
                    <Button type="submit" size="sm" variant="primary" isLoading={isClaiming} disabled={!draft.trim()}>
                        Add domain
                    </Button>
                </div>
                {claimError ? (
                    <p id="workspace-domain-error" role="alert" className="text-xs text-[#C43D3D]">
                        {claimError}
                    </p>
                ) : (
                    <p className="text-xs text-black-500">Your organisation&apos;s own email domain, e.g. the part after @ in your work address. Free email providers and shared domains can&apos;t be added.</p>
                )}
            </form>

            <div className="flex flex-col gap-3">
                <h2 className="text-sm font-semibold text-black-900">Domains</h2>
                {isLoading ? (
                    <p className="text-xs text-black-500">Loading…</p>
                ) : isError ? (
                    <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-[#F3D1D1] bg-[#FBEFEF] px-3 py-3 text-xs text-[#C43D3D]">
                        <span>Your domains couldn&apos;t be loaded. Nothing has been changed.</span>
                        <Button size="sm" variant="v2Button" onClick={() => refetch()}>
                            Try again
                        </Button>
                    </div>
                ) : domains.length === 0 ? (
                    <p className="rounded-md border border-dashed border-black-200 px-3 py-4 text-center text-xs text-black-500">No domains yet. Add your organisation&apos;s email domain above.</p>
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
