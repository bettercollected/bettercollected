import { atom, useAtom } from "jotai";

export enum Plan {
    FREE = 'FREE',
    PRO = 'PRO'
}

export interface UserStatus {
    firstName?: string;
    lastName?: string;
    email: string;
    id: string;
    roles: Array<string>;
    plan: Plan;
    stripeCustomerId?: string;
    stripePaymentId?: string;
    profileImage?: string;
    isAdmin?: boolean;
    isLoading?: boolean;
    tags?: Array<string>;
    is401?: boolean;
}

export const initialAuthState: UserStatus = {
    email: '',
    plan: Plan.FREE,
    roles: [],
    id: '',
    isAdmin: false,
    isLoading: true
};

const initialAuthAtom = atom<UserStatus>(initialAuthState)

export const useAuthAtom = () => {
    const [authState, setAuthState] = useAtom(initialAuthAtom)
    return { authState, setAuthState }
}