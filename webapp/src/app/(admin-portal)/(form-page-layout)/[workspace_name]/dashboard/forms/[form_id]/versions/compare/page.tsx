'use client';

import { useSearchParams } from 'next/navigation';

import VersionCompare from '@app/components/form-versions/version-compare';

export default function Page() {
    const params = useSearchParams();
    return <VersionCompare from={params?.get('from') ?? ''} to={params?.get('to') ?? ''} />;
}
