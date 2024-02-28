import { atom, useAtom } from "jotai";


interface INavbar{
    insertClicked:boolean 
}

const initialNavbarState = atom<INavbar>({
    insertClicked: false
});

export function useNavbarState() {
    const [navbarState, setNavbarState] = useAtom(initialNavbarState);
    return {navbarState, setNavbarState}
}