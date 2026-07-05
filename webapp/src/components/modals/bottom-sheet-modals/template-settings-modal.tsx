
import BottomSheetModalWrapper from '@Components/modals/modal-wrapper/bottom-sheet-modal-wrapper';
import TemplateSettings from '@Components/template/template-settings';

import { IFormTemplateDto } from '@app/models/dtos/template';


export default function TemplateSettingsModal({ template, showTitle = false }: { template: IFormTemplateDto; showTitle?: boolean }) {
    return (
        <BottomSheetModalWrapper>
            <TemplateSettings template={template} showTitle={showTitle} />
        </BottomSheetModalWrapper>
    );
}