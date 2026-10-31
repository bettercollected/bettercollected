import type { RuntimeFlags } from '@app/shared/hocs/runtime-flags-provider';

// What pydantic accepts as true, so SSO_ENABLED means the same here as on the
// backend and auth.
const TRUE_VALUES = new Set(['1', 'true', 't', 'yes', 'y', 'on']);

// Server only. Read per request from the runtime environment (not a
// NEXT_PUBLIC_* variable, which the build inlines), so the same image can turn
// a feature on or off with its environment.
export function readRuntimeFlags(env: Record<string, string | undefined> = process.env): RuntimeFlags {
    return {
        // The same switch the backend and auth use (docs/sso.md).
        ssoEnabled: TRUE_VALUES.has((env.SSO_ENABLED ?? '').trim().toLowerCase())
    };
}
