import { createContext } from 'react';

/**
 * Whether the page is shown as a preview (the builder's, or the creator's preview page) rather than to a
 * respondent. A preview sends nothing anywhere: a question that would call the server while answered (the address
 * lookup) stays local. False outside a form page.
 */
export const PreviewModeContext = createContext(false);
