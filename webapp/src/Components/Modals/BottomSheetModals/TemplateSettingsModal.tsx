import React from 'react';

import BottomSheetModalWrapper from '@Components/Modals/ModalWrappers/BottomSheetModalWrapper';
import TemplateSettings from '@Components/Template/TemplateSettings';

import { IFormTemplateDto } from '@app/models/dtos/template';


export default function TemplateSettingsModal({ template, showTitle = false }: { template: IFormTemplateDto; showTitle?: boolean }) {
    return (
        <BottomSheetModalWrapper>
            <TemplateSettings template={template} showTitle={showTitle} />
        </BottomSheetModalWrapper>
    );
}