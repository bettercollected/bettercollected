'use client';

import { useEffect } from 'react';

import { useRouter } from 'next/navigation';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';

/** Where a form opens: its Responses when it is published and the person may read them (the first thing they came for), else Pages. */
export function landingSection(form: Pick<StandardFormDto, 'isPublished'> | undefined, canReadResponses: boolean): 'responses' | 'preview' {
    return form?.isPublished && canReadResponses ? 'responses' : 'preview';
}

/**
 * The form's own address has no page of its own: it sends the visitor to the section they most likely want. The
 * choice needs the form and the person's permissions, so it waits for both (the shell already shows the form's
 * bar and menu meanwhile) and replaces the history entry, so Back does not return to a blank address.
 */
export default function FormLanding({ base }: { base: string }) {
    const router = useRouter();
    const form = useAppSelector(selectForm);
    const { can, ready } = useWorkspacePermissions();
    const section = form?.formId && ready ? landingSection(form, can(WorkspacePermission.RESPONSE_READ)) : null;

    useEffect(() => {
        if (section) router.replace(`${base}/${section}`);
    }, [section, router, base]);

    return null;
}
