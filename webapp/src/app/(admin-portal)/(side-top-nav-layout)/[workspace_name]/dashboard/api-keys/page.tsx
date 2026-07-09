'use client';

import { useState } from 'react';

import { Check, Copy, KeyRound } from 'lucide-react';

import environments from '@app/configs/environments';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useCreateAPIKeyMutation, useGetAPIKeysQuery, useRevokeAPIKeyMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface APIKey {
    id: string;
    name: string;
    prefix: string;
    scopes: string[];
    revoked: boolean;
    lastUsedAt?: string | null;
}

// Mirrors the backend's VALID_SCOPES — what a key is allowed to do.
const SCOPES: Array<{ key: string; label: string; hint: string }> = [
    { key: 'forms:read', label: 'Read forms', hint: 'List forms and read their structure' },
    { key: 'forms:write', label: 'Create & edit forms', hint: 'Create forms with AI, edit and publish them' },
    { key: 'responses:read', label: 'Read responses', hint: 'List and read form responses' },
    { key: 'deletion_requests:read', label: 'Read deletion requests', hint: 'See pending response-deletion requests' },
    { key: 'deletion_requests:write', label: 'Act on deletion requests', hint: 'Process response-deletion requests' }
];

function CopyButton({ value, label }: { value: string; label: string }) {
    const [copied, setCopied] = useState(false);
    return (
        <button
            type="button"
            aria-label={label}
            onClick={async () => {
                await navigator.clipboard.writeText(value);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
            }}
            className="text-black-500 hover:text-black-800 shrink-0 rounded p-1 transition-colors"
        >
            {copied ? <Check className="h-4 w-4 text-[#0E8A5F]" /> : <Copy className="h-4 w-4" />}
        </button>
    );
}

/**
 * Workspace API keys — the credentials external AI tools (Claude, ChatGPT,
 * anything MCP-capable) use to work with this workspace (plan §2.5).
 * The token is shown exactly once at creation; only its prefix is kept.
 */
export default function APIKeysPage() {
    const workspace = useAppSelector(selectWorkspace);
    const isAdmin = useAppSelector(selectIsAdmin);
    const { toast } = useToast();

    const { data: keys = [], isLoading } = useGetAPIKeysQuery(workspace?.id, { skip: !workspace?.id || !isAdmin });
    const [createKey, { isLoading: isCreating }] = useCreateAPIKeyMutation();
    const [revokeKey] = useRevokeAPIKeyMutation();

    const [name, setName] = useState('');
    const [scopes, setScopes] = useState<string[]>(['forms:read']);
    // The one and only time the full token is visible.
    const [freshToken, setFreshToken] = useState<{ name: string; token: string } | null>(null);

    const mcpUrl = `${environments.API_ENDPOINT_HOST}/mcp`;

    const toggleScope = (scope: string) => {
        setScopes((current) => (current.includes(scope) ? current.filter((s) => s !== scope) : [...current, scope]));
    };

    const handleCreate = async () => {
        const response: any = await createKey({ workspace_id: workspace.id, body: { name: name.trim(), scopes } });
        if (response.data) {
            setFreshToken({ name: response.data.name, token: response.data.token });
            setName('');
            setScopes(['forms:read']);
        } else {
            toast({ description: response.error?.data || 'Could not create the API key. Please try again.', variant: 'destructive' });
        }
    };

    const handleRevoke = async (key: APIKey) => {
        if (!window.confirm(`Revoke "${key.name}"? Anything using it loses access immediately.`)) return;
        const response: any = await revokeKey({ workspace_id: workspace.id, key_id: key.id });
        if (response.data) {
            toast({ description: `Revoked "${key.name}"` });
        } else {
            toast({ description: 'Could not revoke the key. Please try again.', variant: 'destructive' });
        }
    };

    if (!isAdmin) {
        return (
            <div className="px-5 py-6 lg:px-10">
                <p className="text-black-500 text-sm">Only workspace admins can manage API keys.</p>
            </div>
        );
    }

    return (
        <div className="flex w-full max-w-[760px] flex-col gap-8 px-5 py-6 lg:px-10">
            <div className="flex flex-col gap-1.5">
                <p className="text-black-600 max-w-[62ch] text-sm leading-relaxed">
                    API keys let external AI tools — Claude, ChatGPT, or anything that speaks MCP — work with this workspace: create and edit forms, read responses, and check deletion requests. Every action a key takes is scoped, attributed, and logged.
                </p>
            </div>

            <div className="flex flex-col gap-2">
                <h2 className="text-black-900 text-sm font-semibold">MCP endpoint</h2>
                <p className="text-black-600 text-xs leading-relaxed">Point your AI tool&apos;s MCP configuration at this URL, using an API key below as the Bearer token.</p>
                <div className="border-black-200 bg-black-50 flex items-center justify-between gap-3 rounded-md border px-3.5 py-2.5">
                    <code className="text-black-800 truncate text-[13px]">{mcpUrl}</code>
                    <CopyButton value={mcpUrl} label="Copy MCP endpoint URL" />
                </div>
            </div>

            {freshToken && (
                <div className="flex flex-col gap-2 rounded-md border border-[#B7E0CD] bg-[#F0FAF5] p-4">
                    <p className="text-black-900 text-sm font-semibold">Copy the key for “{freshToken.name}” now</p>
                    <p className="text-black-600 text-xs leading-relaxed">This is the only time it will be shown. Store it somewhere safe — if you lose it, revoke this key and create a new one.</p>
                    <div className="border-black-200 flex items-center justify-between gap-3 rounded-md border bg-white px-3.5 py-2.5">
                        <code className="text-black-800 truncate text-[13px]">{freshToken.token}</code>
                        <CopyButton value={freshToken.token} label="Copy API key" />
                    </div>
                    <div>
                        <Button size="sm" variant="v2GhostButton" onClick={() => setFreshToken(null)}>
                            Done — I saved it
                        </Button>
                    </div>
                </div>
            )}

            <div className="flex flex-col gap-3">
                <h2 className="text-black-900 text-sm font-semibold">Create a key</h2>
                <input
                    value={name}
                    maxLength={60}
                    placeholder="What will use this key? e.g. “Claude Desktop”"
                    onChange={(e) => setName(e.target.value)}
                    className="border-black-300 text-black-900 placeholder:text-black-400 focus:border-brand-500 h-10 w-full rounded-md border bg-white px-3.5 text-sm outline-none transition duration-150 focus:shadow-[0_0_0_3px_rgba(36,86,204,0.15)]"
                />
                <div className="flex flex-col gap-1.5">
                    {SCOPES.map((scope) => (
                        <label key={scope.key} className="flex cursor-pointer items-start gap-2.5">
                            <input type="checkbox" checked={scopes.includes(scope.key)} onChange={() => toggleScope(scope.key)} className="mt-0.5 h-4 w-4 cursor-pointer" />
                            <span className="flex flex-col">
                                <span className="text-black-800 text-[13px] font-medium">{scope.label}</span>
                                <span className="text-black-500 text-xs">{scope.hint}</span>
                            </span>
                        </label>
                    ))}
                </div>
                <div>
                    <Button size="medium" variant="primary" isLoading={isCreating} disabled={!name.trim() || scopes.length === 0} onClick={handleCreate}>
                        Create key
                    </Button>
                </div>
            </div>

            <div className="flex flex-col gap-3">
                <h2 className="text-black-900 text-sm font-semibold">Your keys</h2>
                {isLoading ? (
                    <p className="text-black-500 text-xs">Loading…</p>
                ) : keys.length === 0 ? (
                    <p className="text-black-500 border-black-200 rounded-md border border-dashed px-3 py-4 text-center text-xs">No keys yet — create one above to connect an AI tool.</p>
                ) : (
                    <ul className="flex flex-col gap-2">
                        {(keys as APIKey[]).map((key) => (
                            <li key={key.id} className={`border-black-200 flex items-start justify-between gap-3 rounded-md border px-3.5 py-3 ${key.revoked ? 'opacity-60' : ''}`}>
                                <div className="flex min-w-0 flex-col gap-1">
                                    <div className="flex items-center gap-2">
                                        <KeyRound className="text-black-500 h-3.5 w-3.5 shrink-0" />
                                        <span className="text-black-900 truncate text-[13px] font-medium">{key.name}</span>
                                        <code className="text-black-500 text-xs">{key.prefix}…</code>
                                        {key.revoked && <span className="rounded bg-[#FBEFEF] px-1.5 py-0.5 text-[10.5px] font-medium text-[#C43D3D]">Revoked</span>}
                                    </div>
                                    <div className="flex flex-wrap items-center gap-1.5">
                                        {key.scopes.map((scope) => (
                                            <span key={scope} className="bg-black-100 text-black-600 rounded px-1.5 py-0.5 text-[10.5px]">
                                                {scope}
                                            </span>
                                        ))}
                                        <span className="text-black-400 text-[10.5px]">{key.lastUsedAt ? `Last used ${new Date(key.lastUsedAt).toLocaleString()}` : 'Never used'}</span>
                                    </div>
                                </div>
                                {!key.revoked && (
                                    <button type="button" onClick={() => handleRevoke(key)} className="text-black-500 shrink-0 rounded px-2 py-1 text-xs transition-colors hover:bg-[#FBEFEF] hover:text-[#C43D3D]">
                                        Revoke
                                    </button>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}
