import { useState } from 'react';

/**
 * True from the moment `chosen` turns on after the control has been shown,
 * until it turns off again. A control that is already chosen when it first
 * renders (a page revisited, an answer prefilled) is not "just chosen", so
 * its selection motion plays on a respondent's own change only, never on
 * mount. The state is derived during render, so the animated element
 * appears with its animation already applied (no flash at full size first).
 */
export default function useJustChosen(chosen: boolean): boolean {
    const [previous, setPrevious] = useState(chosen);
    const [just, setJust] = useState(false);
    if (previous !== chosen) {
        setPrevious(chosen);
        setJust(chosen);
    }
    return just;
}
