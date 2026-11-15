'use client';

import React from 'react';
import { useTranslation } from 'react-i18next';


import EmptyState from '@app/components/ui/empty-state';
import { Button } from '@app/shadcn/components/ui/button';
import WorkspaceFormCard from '@app/components/workspace-dashboard/workspace-form-card';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import NewFormButton from '@app/views/atoms/new-form-button';
import { useRouter } from 'next/navigation';

interface IWorkspaceDashboardFormsCardProps {
    workspaceForms: any;
    workspace: WorkspaceDto;
    hasCustomDomain: boolean;
    showPinned?: boolean;
    showEmpty?: boolean;
    /** Empties the search that found nothing. */
    onClearSearch?: () => void;
}

export default function WorkspaceDashboardFormsCard({ workspaceForms, workspace, hasCustomDomain, showPinned = false, showEmpty = false, onClearSearch }: IWorkspaceDashboardFormsCardProps) {
    const { t } = useTranslation();
    const forms = workspaceForms;
    const router = useRouter()

    return (
        <div className="w-full mb-4 flex flex-col gap-5 h-fit">
            {forms?.length === 0 ? (
                showEmpty ? (
                    // a search with no match: a clear line and the way back, no picture
                    <EmptyState
                        illustration={false}
                        title={t('STAFF.EMPTY_STATE.SEARCH_TITLE')}
                        description={t('STAFF.EMPTY_STATE.SEARCH_TEXT')}
                        action={
                            onClearSearch && (
                                <Button size="medium" onClick={onClearSearch}>
                                    {t('STAFF.EMPTY_STATE.SEARCH_CLEAR')}
                                </Button>
                            )
                        }
                    />
                ) : (
                    <EmptyState title={t('STAFF.EMPTY_STATE.FORMS_TITLE')} description={t('STAFF.EMPTY_STATE.FORMS_TEXT')} action={<NewFormButton />} />
                )
            ) : (
                <div className="flex flex-col gap-6">
                    {forms?.length !== 0 &&
                        forms?.map((form: StandardFormDto, index: number) => (
                            <div key={form.formId} onClick={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                router.push(`/${workspace.workspaceName}/dashboard/forms/${form.formId}?view=Responses`)
                            }}>
                                <WorkspaceFormCard index={index} showPinned={showPinned} form={form} workspace={workspace} hasCustomDomain={hasCustomDomain} />
                            </div>
                        ))}
                </div>
            )}
        </div>
    );
}
