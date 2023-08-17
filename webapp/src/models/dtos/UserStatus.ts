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
}
