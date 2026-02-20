'use client';

import TemplateSection from '@Components/Template/TemplateSection';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetTemplatesQuery } from '@app/store/template/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { useTranslation } from 'react-i18next';

export default function TemplatesClient({ predefined_templates }: { predefined_templates: any[] }) {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);

    console.log('predefined_templates', predefined_templates);

    let p = [...(predefined_templates || [])];
    const { data: v2Forms } = useGetTemplatesQuery(
        { workspace_id: workspace?.id, v2: true },
        { skip: !workspace?.id }
    );

    return (
        <>
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
                    templates={v2Forms}
                />
            )}
        </>
    );
}
