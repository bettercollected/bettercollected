import React from 'react';

import TemplateSettings from '@Components/Template/TemplateSettings';

import BottomSheetModalWrapper from '@app/components/modal-views/full-screen-modals/BottomSheetModalWrapper';
import { IFormTemplateDto } from '@app/models/dtos/template';

export default function TemplateSettingsFullModalView({ template, showTitle = false }: { template: IFormTemplateDto; showTitle?: boolean }) {
    return (
        <BottomSheetModalWrapper>
            <TemplateSettings template={template} showTitle={showTitle} />
        </BottomSheetModalWrapper>
    );
}
