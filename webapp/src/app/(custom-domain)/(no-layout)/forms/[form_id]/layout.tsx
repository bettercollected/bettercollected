import React from 'react';

import RespondentDocumentLanguage from '@app/components/form/respondent-document-language';
import RespondentTypeface from '@app/components/form/respondent-typeface';

// A form on a workspace's custom domain keeps the form typeface and the
// respondent's page language, like the same form on the form domain
// (DESIGN.md §2).
export default function CustomDomainFormLayout({ children }: { children: React.ReactNode }) {
    return (
        <>
            <RespondentDocumentLanguage />
            <RespondentTypeface>{children}</RespondentTypeface>
        </>
    );
}
