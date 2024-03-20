'use client';

import Form from '@app/views/organism/Form/Form';

export default function FormPage({
    params
}: {
    params: { formId: string; workspaceName: string };
}) {
    return <Form />;
}
