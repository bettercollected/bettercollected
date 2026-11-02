'use client';

import { use } from 'react';

import VersionView from '@app/components/form-versions/version-view';

export default function Page({ params }: { params: Promise<{ version: string }> }) {
    const { version } = use(params);
    const number = /^\d{1,9}$/.test(version) ? Number(version) : 0;
    return <VersionView version={number} />;
}
