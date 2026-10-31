'use client';

import React, { createContext, useContext } from 'react';

// Feature switches the server reads from its environment on every request
// (src/lib/runtime-flags.ts) and hands to client components, so one image
// serves every deployment: no rebuild to turn a feature on.
export interface RuntimeFlags {
    ssoEnabled: boolean;
}

const RuntimeFlagsContext = createContext<RuntimeFlags>({ ssoEnabled: false });

export default function RuntimeFlagsProvider({ flags, children }: Readonly<{ flags: RuntimeFlags; children: React.ReactNode | React.ReactNode[] }>) {
    return <RuntimeFlagsContext.Provider value={flags}>{children}</RuntimeFlagsContext.Provider>;
}

/** Enterprise single sign-on (docs/sso.md): SSO_ENABLED on the webapp. */
export function useSsoEnabled(): boolean {
    return useContext(RuntimeFlagsContext).ssoEnabled;
}
