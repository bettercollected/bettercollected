import _ from 'lodash';

import { UserStatus } from '@app/models/dtos/UserStatus';
import { WorkspaceMembersDto } from '@app/models/dtos/WorkspaceMembersDto';


export function getFullNameFromUser(user: UserStatus | WorkspaceMembersDto) {
    return _.capitalize(user.firstName) + ' ' + _.capitalize(user.lastName);
}