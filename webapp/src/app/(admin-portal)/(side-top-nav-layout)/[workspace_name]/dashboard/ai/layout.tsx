import React from 'react';

import AISectionLayout from './_components/ai-section-layout';

export default async function Layout(props: { children: React.ReactNode; params: Promise<{ workspace_name: string }> }) {
    const { workspace_name } = await props.params;
    return <AISectionLayout workspaceName={workspace_name}>{props.children}</AISectionLayout>;
}
