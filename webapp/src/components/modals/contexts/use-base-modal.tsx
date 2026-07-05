import { PrimitiveAtom, useAtom } from 'jotai';

export function useBaseModal<T>(
    atom: PrimitiveAtom<{
        isOpen: boolean;
        view: T | '';
        modalProps: any;
    }>
) {
    const [state, setState] = useAtom(atom);
    const openModal = (view: T, modalProps: any = null) =>
        setState({
            ...state,
            isOpen: true,
            view,
            modalProps
        });
    const closeModal = () => {
        setState({ ...state, isOpen: false, modalProps: null, view: '' });
    };

    return {
        ...state,
        openModal,
        closeModal,
        setState
    };
}