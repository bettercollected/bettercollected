export interface WorkspaceMembersDto {
    id: string;
    firstName: string;
    lastName: string;
    roles: Array<string>;
    joined: string;
    email: string;
    profileImage?: string;
}
