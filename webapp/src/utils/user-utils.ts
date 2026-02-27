import _ from 'lodash';

import { UserStatus } from '@app/models/dtos/user-status';
import { WorkspaceMembersDto } from '@app/models/dtos/workspace-member-dto';

export function getFullNameFromUser(user: UserStatus | WorkspaceMembersDto) {
    if (user.firstName || user.lastName) return _.capitalize(user.firstName) + ' ' + _.capitalize(user.lastName);
    return user.email;
}
