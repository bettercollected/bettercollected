import { createContext, useContext } from 'react';

import { AppTheme } from '@app/lib/app-theme';

/**
 * The app theme the page is drawn in: set by `AppThemeScope` (the workspace layout), `null` everywhere else (the real
 * respondent page, which has no scope). A respondent's form root reads it to decide whether the app roles it must not
 * inherit need resetting (`formRootProps`), so a form outside any scope renders exactly the markup it always did.
 */
export const AppThemeContext = createContext<AppTheme | null>(null);

export const useInAppThemeScope = (): boolean => useContext(AppThemeContext) !== null;

/**
 * The app theme in scope: `null` outside any scope. `AppThemeScope` renders on the server with the value the server
 * read, so a component that reads this draws the right theme in the first HTML, with no frame in the wrong one.
 */
export const useAppTheme = (): AppTheme | null => useContext(AppThemeContext);
