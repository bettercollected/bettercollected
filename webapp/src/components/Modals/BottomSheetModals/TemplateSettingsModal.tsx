
import BottomSheetModalWrapper from '@app/components/Modals/ModalWrappers/BottomSheetModalWrapper';
import TemplateSettings from '@app/components/Template/TemplateSettings';

import { IFormTemplateDto } from '@app/models/dtos/template';


export default function TemplateSettingsModal({ template, showTitle = false }: { template: IFormTemplateDto; showTitle?: boolean }) {
    return (
        <BottomSheetModalWrapper>
            <TemplateSettings template={template} showTitle={showTitle} />
        </BottomSheetModalWrapper>
    );
}