'use client';

import Form from '@app/views/organism/Form/Form';

export default function ResponsePage({
    searchParams
}: {
    searchParams: { responseId?: string };
}) {
    return <Form isPreviewMode />;
}
