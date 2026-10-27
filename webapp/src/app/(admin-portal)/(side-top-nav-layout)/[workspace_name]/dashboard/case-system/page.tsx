'use client';

import React from 'react';

import { useTranslation } from 'react-i18next';

import ServicesSection from '@app/components/registration/services-section';
import { useRegistrationEnabled } from '@app/components/registration/use-registration-enabled';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';

/**
 * Workspace settings, "Case system": where submissions can be sent. Owners
 * and admins only (workspace.manage), and only while this server has the
 * feature on; the sidebar item is hidden under the same two conditions.
 */
export default function CaseSystemPage() {
    const { t } = useTranslation('builder');
    const { can, ready } = useWorkspacePermissions();
    const { enabled, isLoading } = useRegistrationEnabled();

    if (!ready || isLoading) return <div className="pb-10 text-sm text-black-600">{t('REGISTRATION.LOADING')}</div>;

    if (!can(WorkspacePermission.WORKSPACE_MANAGE)) {
        return <p className="pb-10 text-sm text-black-700">{t('REGISTRATION.SERVICES.ONLY_ADMINS')}</p>;
    }
    if (!enabled) {
        return <p className="pb-10 text-sm text-black-700">{t('REGISTRATION.SERVICES.TURNED_OFF')}</p>;
    }
    return <ServicesSection />;
}
