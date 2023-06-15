import _ from 'lodash';

import { UserStatus } from '@app/models/dtos/UserStatus';

export function getFullNameFromUser(user: UserStatus) {
    return _.capitalize(user.firstName) + ' ' + _.capitalize(user.lastName);
}
