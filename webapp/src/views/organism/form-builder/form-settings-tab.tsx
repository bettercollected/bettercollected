'use client';

import HiddenFieldsEditor from '@app/views/molecules/form-builder/hidden-fields-editor';
import QuestionNumberingSetting from '@app/views/molecules/form-builder/question-numbering-setting';
import TrustSettingsEditor from '@app/views/molecules/form-builder/trust-settings-editor';

/**
 * Form-wide settings: hidden fields, question numbering, trust & privacy.
 * They used to live at the bottom of the Page tab, which made one endless
 * scroll where page-scoped and form-scoped settings were indistinguishable —
 * and they were only reachable from content pages.
 */
export default function FormSettingsTab() {
    return (
        <>
            <HiddenFieldsEditor />
            <div className="border-t border-black-300">
                <QuestionNumberingSetting />
            </div>
            <div className="border-t border-black-300">
                <TrustSettingsEditor />
            </div>
        </>
    );
}
