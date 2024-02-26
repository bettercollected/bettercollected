import _ from 'lodash';

import { UserStatus } from '@app/models/dtos/UserStatus';
import { WorkspaceMembersDto } from '@app/models/dtos/WorkspaceMembersDto';

export function getFullNameFromUser(user: UserStatus | WorkspaceMembersDto) {
    if (user.firstName || user.lastName) return _.capitalize(user.firstName) + ' ' + _.capitalize(user.lastName);
    return user.email;
}
