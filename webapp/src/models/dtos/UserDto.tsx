export interface UserDto {
    first_name?: string;
    last_name?: string;
    profile_image?: string;
    email: string;
    roles: Array<string>;
    plan: Plans;
    stripe_customer_id?: string;
    stripe_payment_id?: string;
}

export enum Plans {
    FREE = 'FREE',
    PRO = 'PRO'
}
