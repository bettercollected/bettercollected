import { ResponderGroupDto } from '@app/models/dtos/groups';

export const isEmailInGroup = (group: ResponderGroupDto, email: string) => {
    if (group.emails.includes(email)) return true;
};

export const isFormAlreadyInGroup = (groups: any, groupId: string) => {
    if (groups?.filter((formGroup: ResponderGroupDto) => formGroup.id === groupId).length !== 0) return true;
};
