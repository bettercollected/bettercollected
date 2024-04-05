import { atom, useAtom } from 'jotai';

interface INavbar {
    insertClicked: boolean;
    multiplePages: boolean;
}

const initialNavbarState = atom<INavbar>({
    insertClicked: false,
    multiplePages: true
});

export function useNavbarState() {
    const [navbarState, setNavbarState] = useAtom(initialNavbarState);
    return { navbarState, setNavbarState };
}
