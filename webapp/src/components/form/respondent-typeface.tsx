'use client';

import React, { useEffect } from 'react';

/**
 * Respondent routes keep the typeface forms were published with (Public Sans,
 * `font-form`), while the app around them uses Instrument Sans (DESIGN.md §2).
 * The wrapper sets it from the first server-rendered paint; the body class
 * covers what portals out of the form (date popovers, menus, toasts).
 */
export default function RespondentTypeface({ children }: { children: React.ReactNode }) {
    useEffect(() => {
        document.body.classList.add('respondent-typeface');
        return () => document.body.classList.remove('respondent-typeface');
    }, []);
    return <div className="font-form contents">{children}</div>;
}
