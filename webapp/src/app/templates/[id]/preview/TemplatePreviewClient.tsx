'use client';

import React from 'react';
import BetterCollectedForm from '@app/Components/Form/BetterCollectedForm';
import { useGetTemplateByIdQuery } from '@app/store/template/api';
import { convertFormTemplateToStandardForm } from '@app/utils/convertDataType';

export default function TemplatePreviewClient({ templateId }: { templateId: string }) {
    const { data } = useGetTemplateByIdQuery({
        template_id: templateId
    });
    return (
        <div className="h-[100vh] max-h-[100vh] overflow-hidden bg-white">
            {data && <BetterCollectedForm isDisabled form={convertFormTemplateToStandardForm(data)} />}
        </div>
    );
}
