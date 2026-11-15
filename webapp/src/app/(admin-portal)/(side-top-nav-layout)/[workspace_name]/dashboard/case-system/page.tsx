'use client';

import React from 'react';

import { useTranslation } from 'react-i18next';

import ServicesSection from '@app/components/registration/services-section';
import { useRegistrationEnabled } from '@app/components/registration/use-registration-enabled';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { PageSurface } from '@app/components/ui/page-surface';

/**
 * Workspace settings, "Case system": where submissions can be sent. Owners
 * and admins only (workspace.manage), and only while this server has the
 * feature on; the sidebar item is hidden under the same two conditions.
 */
export default function CaseSystemPage() {
    const { t } = useTranslation('builder');
    const { can, ready } = useWorkspacePermissions();
    const { enabled, isLoading } = useRegistrationEnabled();

    const message = (text: string) => <p className="text-sm text-black-700">{text}</p>;
    let content: React.ReactNode = <ServicesSection />;
    if (!ready || isLoading) content = <p className="text-sm text-black-600">{t('REGISTRATION.LOADING')}</p>;
    else if (!can(WorkspacePermission.WORKSPACE_MANAGE)) content = message(t('REGISTRATION.SERVICES.ONLY_ADMINS'));
    else if (!enabled) content = message(t('REGISTRATION.SERVICES.TURNED_OFF'));
    return <PageSurface narrow>{content}</PageSurface>;
}
