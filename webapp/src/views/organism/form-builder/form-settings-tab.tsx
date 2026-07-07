'use client';

import HiddenFieldsEditor from '@app/views/molecules/form-builder/hidden-fields-editor';
import TrustSettingsEditor from '@app/views/molecules/form-builder/trust-settings-editor';

/**
 * Form-wide settings (hidden fields, trust & privacy) get their own tab.
 * They used to live at the bottom of the Page tab, which made one endless
 * scroll where page-scoped and form-scoped settings were indistinguishable —
 * and they were only reachable from content pages.
 */
export default function FormSettingsTab() {
    return (
        <>
            <HiddenFieldsEditor />
            <div className="border-t">
                <TrustSettingsEditor />
            </div>
        </>
    );
}
