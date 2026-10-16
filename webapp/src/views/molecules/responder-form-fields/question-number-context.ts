import { createContext } from 'react';

/**
 * The Leaflet style's question numbers for the page being shown (field id →
 * "2.1"), and whether they may hang outside the text measure (wide, centred
 * pages). Absent everywhere else, so other styles render no numbers.
 */
export const QuestionNumberContext = createContext<{ numbers: Record<string, string>; hang: boolean } | null>(null);
