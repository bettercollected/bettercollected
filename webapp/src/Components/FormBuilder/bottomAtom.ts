import {atom, useAtom} from 'jotai';

interface IButtonAtom {
    show: boolean;
}

const initIButtonProps = {
    show: false
}

const buttonAtom = atom<IButtonAtom>(initIButtonProps);

export default function useFormBuilderButtonState() {
    const [visibility, setVisibility] = useAtom(buttonAtom)
    const setShowButton = () => {
        setVisibility({show: true})
    }
    const setHideButton = () => {
        setVisibility({show: false})
    }
    return {visibility, setShowButton, setHideButton};
}