'use client';

import React, { createContext, useContext } from 'react';

// Feature switches the server reads from its environment on every request
// (src/lib/runtime-flags.ts) and hands to client components, so one image
// serves every deployment: no rebuild to turn a feature on.
export interface RuntimeFlags {
    ssoEnabled: boolean;
    /** Field rules may be created and changed in the builder (FIELD_RULES_ENABLED, the backend's switch). */
    fieldRulesEnabled?: boolean;
}

const RuntimeFlagsContext = createContext<RuntimeFlags>({ ssoEnabled: false, fieldRulesEnabled: false });

export default function RuntimeFlagsProvider({ flags, children }: Readonly<{ flags: RuntimeFlags; children: React.ReactNode | React.ReactNode[] }>) {
    return <RuntimeFlagsContext.Provider value={flags}>{children}</RuntimeFlagsContext.Provider>;
}

/** Enterprise single sign-on (docs/sso.md): SSO_ENABLED on the webapp. */
export function useSsoEnabled(): boolean {
    return useContext(RuntimeFlagsContext).ssoEnabled;
}

/**
 * Field rules (docs/spec/README.md): FIELD_RULES_ENABLED on the webapp, the
 * same switch as the backend's. Off, the builder hides the rules editor
 * (the server would refuse what it saves); rules already on questions are
 * still enforced and still shown.
 */
export function useFieldRulesEnabled(): boolean {
    return !!useContext(RuntimeFlagsContext).fieldRulesEnabled;
}
