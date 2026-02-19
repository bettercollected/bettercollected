'use client';

import React from 'react';
import { useTranslation } from 'react-i18next';
import TemplateSection from '@Components/Template/TemplateSection';
import SidebarLayout from '@app/Components/sidebar/sidebar-layout';
import { useGetTemplatesQuery } from '@app/store/template/api';
import { useAppSelector } from '@app/store/hooks';
import { selectAuth } from '@app/store/auth/slice';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function TemplatesClient({ predefined_templates }: { predefined_templates: any[] }) {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);

    let p = [...(predefined_templates || [])];
    if (p.length > 7) {
        p = p.slice(0, 7);
    }

    const { data: v2Forms } = useGetTemplatesQuery(
        { workspace_id: workspace?.id, v2: true },
        { skip: !workspace?.id }
    );

    return (
        <SidebarLayout boxClassName="h-full">
            {predefined_templates && Array.isArray(predefined_templates) && predefined_templates.length > 0 && (
                <TemplateSection
                    title={t('TEMPLATE.DEFAULT')}
                    templates={auth?.roles?.includes('ADMIN') ? p : []}
                    className="h-[400px]"
                />
            )}
            {auth?.roles?.includes('ADMIN') && (
                <TemplateSection
                    title={t('TEMPLATE.YOUR_WORKSPACE') + ' v2'}
                    showButtons={false}
                    templates={v2Forms}
                />
            )}
        </SidebarLayout>
    );
}
