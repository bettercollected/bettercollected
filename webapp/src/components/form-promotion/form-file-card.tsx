'use client';

import { useState } from 'react';

import { useTranslation } from 'react-i18next';

import { SettingRow } from '@app/components/dashboard/form-settings';
import { buttonClassName } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useGetAllMineWorkspacesQuery } from '@app/store/workspaces/api';
import { saveFormFile, useDownloadFormFileMutation } from '@app/store/workspaces/form-promotion-api';

function formatDay(value: string, language: string): string {
    // the server sends UTC without a zone mark
    const date = new Date(/(Z|[+-]\d\d:?\d\d)$/.test(value) ? value : `${value}Z`);
    if (Number.isNaN(date.getTime())) return '';
    return new Intl.DateTimeFormat(language, { dateStyle: 'medium' }).format(date);
}

/** Settings, Advanced: "Form file", the form's document as a download (it holds no answer). Shown only while the server has copying on. */
export function FormFileCard({ workspaceId, formId }: { workspaceId: string; formId: string }) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const [download, { isLoading }] = useDownloadFormFileMutation();
    const [refusal, setRefusal] = useState<string | null>(null);

    const onDownload = async () => {
        setRefusal(null);
        try {
            saveFormFile(await download({ workspaceId, formId }).unwrap());
            toast({ description: t('FORM_PROMOTION.FILE.DOWNLOADED').toString() });
        } catch (error) {
            // a restricted form's structure leaves only through an owner, an admin or its creator
            setRefusal((error as { data?: { code?: string } })?.data?.code === 'promotion_from_restricted_form' ? t('FORM_PROMOTION.FILE.ERROR_RESTRICTED') : t('FORM_PROMOTION.FILE.ERROR'));
        }
    };

    return (
        <div>
            <div className="flex flex-col divide-y divide-black-300">
                <SettingRow title={t('FORM_PROMOTION.FILE.TITLE')} description={t('FORM_PROMOTION.FILE.TEXT')}>
                    <button
                        type="button"
                        data-testid="form-file-download"
                        disabled={isLoading}
                        onClick={() => void onDownload()}
                        // the visible word first, then what it is for (the row names the button by its title)
                        aria-label={`${t('FORM_PROMOTION.FILE.DOWNLOAD')}: ${t('FORM_PROMOTION.FILE.TITLE')}`}
                        className={`${buttonClassName({ variant: 'v2Button' })} min-h-[44px] md:min-h-[40px]`}
                    >
                        {isLoading ? t('FORM_PROMOTION.FILE.DOWNLOADING') : t('FORM_PROMOTION.FILE.DOWNLOAD')}
                    </button>
                </SettingRow>
            </div>
            {refusal && (
                <p role="alert" data-testid="form-file-error" className="mt-2 text-sm">
                    {refusal}
                </p>
            )}
        </div>
    );
}

/**
 * "Copied from <workspace> on <date>": where the form was last copied from. The workspace is named only when the viewer
 * is a member of it (it is in their own list), else "another workspace". The server sends the mark to people who may edit
 * the form only, so this is for editors.
 */
export function PromotedFromLine({ promotedFrom, language }: { promotedFrom: { workspaceId: string; at: string }; language: string }) {
    const { t } = useTranslation();
    const mine = useGetAllMineWorkspacesQuery();
    const date = formatDay(promotedFrom.at, language);
    const name = (Array.isArray(mine.data) ? (mine.data as Array<{ id: string; title?: string }>) : []).find((w) => w?.id === promotedFrom.workspaceId)?.title;
    return (
        <p data-testid="promoted-from-line" className="text-sm leading-relaxed text-black-700">
            {name ? t('FORM_PROMOTION.ORIGIN.FROM_WORKSPACE', { workspace: name, date }) : t('FORM_PROMOTION.ORIGIN.FROM_OTHER', { date })}
        </p>
    );
}
