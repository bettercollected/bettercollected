import { createContext } from 'react';

/**
 * The question numbers for the page being shown (field id → "2.1"), and
 * whether they may hang outside the text measure (wide, centred pages).
 * The Leaflet style always numbers; other styles number when the form has
 * question numbering on (`plain`: set in the form's own label style, not
 * the Leaflet serif). Absent otherwise, so no numbers render.
 */
export const QuestionNumberContext = createContext<{ numbers: Record<string, string>; hang: boolean; plain?: boolean } | null>(null);
