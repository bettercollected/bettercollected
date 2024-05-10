'use client';

import { atom, useAtom } from 'jotai';

export type SetAtom<Args extends any[], Result> = (...args: Args) => Result;

export interface ActiveFormBuilderComponent {
    id: string;
    index: number;
}

const activeField = atom<ActiveFormBuilderComponent | null>(null);

export function useActiveFieldComponent() {
    const [activeFieldComponent, setActiveFieldComponent] = useAtom(activeField);

    return { activeFieldComponent, setActiveFieldComponent };
}

const activeSlide = atom<ActiveFormBuilderComponent | null>({
    id: 'welcome-page',
    index: -10
});

export function useActiveSlideComponent() {
    const [activeSlideComponent, setActiveSlideComponent] = useAtom(activeSlide);
    return { activeSlideComponent, setActiveSlideComponent };
}

const activeThankYouPage = atom<ActiveFormBuilderComponent | null>({
    id: '',
    index: 0
});

export function useActiveThankYouPageComponent() {
    const [activeThankYouPageComponent, setActiveThankYouPageComponent] =
        useAtom(activeThankYouPage);
    return { activeThankYouPageComponent, setActiveThankYouPageComponent };
}
