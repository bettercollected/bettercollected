import _ from 'lodash';

export function getFullNameFromUser(user: any) {
    return _.capitalize(user.first_name) + ' ' + _.capitalize(user.last_name);
}
