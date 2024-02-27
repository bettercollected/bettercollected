import { atom, useAtom } from 'jotai';

interface IFormState {
    title: string;
    description?: string;
    thankYouMessage?: string;
    thankYouButtonText?: string;
    buttonText?: string;
}

const initialFormState = atom<IFormState>({
    title: '',
    description: undefined,
    thankYouMessage: undefined,
    thankYouButtonText: '',
    buttonText: undefined
});

export function useFormState() {
    const [formState, setFormState] = useAtom(initialFormState);

    const setFormTitle = (title: string) => {
        setFormState({ ...formState, title });
    };

    const setFormDescription = (description: string) => {
        setFormState({ ...formState, description });
    };
    
    return { formState, setFormState, setFormDescription, setFormTitle };
}
