import { atom, useAtom } from 'jotai';

interface INavbar {
    insertClicked: boolean;
    multiplePages: boolean;
    /**
     * Whether the navbar's Insert dropdown is open. Lives here (not local
     * navbar state) so empty-canvas affordances can open it too.
     */
    insertMenuOpen?: boolean;
}

const initialNavbarState = atom<INavbar>({
    insertClicked: false,
    multiplePages: true,
    insertMenuOpen: false
});

export function useNavbarState() {
    const [navbarState, setNavbarState] = useAtom(initialNavbarState);
    return { navbarState, setNavbarState };
}
