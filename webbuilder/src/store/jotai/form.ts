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
    return { formState, setFormState };
}
