'use client';

import { useState } from 'react';

import { FileUp as ImportIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';

import ResponseImportDialog from './response-import-dialog';

interface Props {
    workspaceId: string;
    formId: string;
}

/** "Import responses" on a form's responses screen: shown only with the switch on and response.import. */
export default function ResponseImportControl({ workspaceId, formId }: Props) {
    const { t } = useTranslation();
    const [open, setOpen] = useState(false);
    return (
        <>
            <Button className="whitespace-nowrap" variant="v2Button" icon={<ImportIcon className="h-4 w-4" />} onClick={() => setOpen(true)}>
                {t('RESPONSE_IMPORT.BUTTON')}
            </Button>
            {open && <ResponseImportDialog open={open} onOpenChange={setOpen} workspaceId={workspaceId} formId={formId} />}
        </>
    );
}
