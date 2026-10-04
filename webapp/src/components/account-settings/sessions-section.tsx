'use client';

import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useGetSessionsQuery, useRevokeOtherSessionsMutation, useRevokeSessionMutation } from '@app/store/auth/api';
import { AuthSession } from '@app/store/auth/types';

/** A short, human label for a browser's user agent ("Firefox on Linux"). */
export function describeUserAgent(userAgent?: string): string {
    if (!userAgent) return 'Unknown device';
    const browser = /Edg\//.test(userAgent)
        ? 'Edge'
        : /Firefox\//.test(userAgent)
          ? 'Firefox'
          : /Chrome\//.test(userAgent)
            ? 'Chrome'
            : /Safari\//.test(userAgent)
              ? 'Safari'
              : /curl\//.test(userAgent)
                ? 'curl'
                : 'Browser';
    const os = /Android/.test(userAgent)
        ? 'Android'
        : /iPhone|iPad/.test(userAgent)
          ? 'iOS'
          : /Windows/.test(userAgent)
            ? 'Windows'
            : /Mac OS X|Macintosh/.test(userAgent)
              ? 'macOS'
              : /Linux/.test(userAgent)
                ? 'Linux'
                : '';
    return os ? `${browser} on ${os}` : browser;
}

function formatDate(value?: string) {
    return value ? new Date(value).toLocaleString() : '';
}

/**
 * Where the user is signed in. Ending a session signs that browser out at its
 * next token refresh (within minutes).
 */
export default function SessionsSection() {
    const { toast } = useToast();
    const { data: sessions = [], isLoading } = useGetSessionsQuery();
    const [revokeSession] = useRevokeSessionMutation();
    const [revokeOthers, { isLoading: isRevokingOthers }] = useRevokeOtherSessionsMutation();
    const others = (sessions as AuthSession[]).filter((session) => !session.current);

    const handleRevoke = async (session: AuthSession) => {
        const response: any = await revokeSession(session.id);
        if (response.error) {
            toast({ description: 'Could not sign that session out. Please try again.', variant: 'destructive' });
        } else if (session.current) {
            window.location.href = '/login';
        }
    };

    const handleRevokeOthers = async () => {
        const response: any = await revokeOthers();
        if (response.error) {
            toast({ description: 'Could not sign out the other sessions. Please try again.', variant: 'destructive' });
        } else {
            toast({ description: 'Signed out everywhere else.' });
        }
    };

    return (
        <div className="border-black-200 flex max-w-[640px] flex-col gap-4 rounded-lg border bg-white p-6">
            <div className="flex flex-col gap-1">
                <h2 className="text-black-900 text-sm font-semibold">Where you&apos;re signed in</h2>
                <p className="text-black-600 text-xs leading-relaxed">Sign out a browser you no longer use. It loses access within a few minutes.</p>
            </div>

            {isLoading ? (
                <p className="text-black-500 text-xs">Loading…</p>
            ) : (
                <ul className="flex flex-col gap-1.5">
                    {(sessions as AuthSession[]).map((session) => (
                        <li key={session.id} className="border-black-200 flex items-center justify-between gap-3 rounded-md border px-3 py-2">
                            <div className="min-w-0">
                                <p className="text-black-800 text-[13px] leading-relaxed">
                                    {describeUserAgent(session.userAgent)}
                                    {session.method === 'sso' && <span className="text-black-500"> · Single sign-on</span>}
                                    {session.current && <span className="text-black-500"> · This browser</span>}
                                </p>
                                <p className="text-black-400 text-[10.5px]">
                                    Signed in {formatDate(session.createdAt)}
                                    {session.lastRefreshedAt ? ` · Last active ${formatDate(session.lastRefreshedAt)}` : ''}
                                </p>
                            </div>
                            <Button variant="ghost" className="text-black-700 shrink-0 px-2 py-1 text-xs" onClick={() => handleRevoke(session)}>
                                Sign out
                            </Button>
                        </li>
                    ))}
                </ul>
            )}

            {others.length > 0 && (
                <div>
                    <Button variant="ghost" disabled={isRevokingOthers} className="rounded bg-red-100 px-4 py-3 text-xs !text-red-500 hover:bg-red-200" onClick={handleRevokeOthers}>
                        Sign out everywhere else
                    </Button>
                </div>
            )}
        </div>
    );
}
