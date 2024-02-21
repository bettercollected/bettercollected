'use client';

import { atom, useAtom } from 'jotai';

interface ActiveFormBuilderComponent {
    id: string;
    index: number;
}

const activeField = atom<ActiveFormBuilderComponent | null>(null);

export function useActiveFieldComponent() {
    const [activeFieldComponent, setActiveFieldComponent] = useAtom(activeField);

    return { activeFieldComponent, setActiveFieldComponent };
}

const activeSlide = atom<ActiveFormBuilderComponent | null>(null);

export function useActiveSlideComponent() {
    const [activeSlideComponent, setActiveSlideComponent] = useAtom(activeSlide);
    return { activeSlideComponent, setActiveSlideComponent };
}
