import React from 'react';

import RespondentTypeface from '@app/components/form/respondent-typeface';

// A form on a workspace's custom domain keeps the form typeface, like the
// same form on the form domain (DESIGN.md §2).
export default function CustomDomainFormLayout({ children }: { children: React.ReactNode }) {
    return <RespondentTypeface>{children}</RespondentTypeface>;
}
