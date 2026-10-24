import React from 'react';

import SSOSectionLayout from './_components/sso-section-layout';

export default async function Layout(props: { children: React.ReactNode; params: Promise<{ workspace_name: string }> }) {
    const { workspace_name } = await props.params;
    return <SSOSectionLayout workspaceName={workspace_name}>{props.children}</SSOSectionLayout>;
}
