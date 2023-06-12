import _ from 'lodash';

import { buttonConstant } from '@app/constants/locales/button';
import { formConstant } from '@app/constants/locales/form';

/**
 * Validation method to check if the given value is undefined or not.
 * @description - Uses lodash's `isUndefined` method to check the value
 *
 * @param {any} data - Data can be of any type (string, number,...)
 *
 * @returns {boolean} - Returns true if value is undefined, else false
 * @author Bibishan Pandey
 */
export function isUndefined(data: unknown): boolean {
    return _.isUndefined(data);
}

/**
 * Validation method to check if the given value is null or not.
 * @description - Uses lodash's `isNull` method to check the value
 *
 * @param {any} data - Data can be of any type (string, number,...)
 *
 * @returns {boolean} - Returns true if value is null, else false
 * @author Bibishan Pandey
 */
export function isNull(data: unknown): boolean {
    return _.isNull(data);
}

/**
 * Validation method to check if the given value is neither undefined nor null.
 * @description - Uses another validation helper method `isUndefined` and `isNull`.
 *
 * @see isUndefined
 * @see isNull
 *
 * @param {any} data - Data can be of any type (string, number,...)
 *
 * @returns {boolean} - Returns true if value is neither undefined nor null, else false
 * @author Bibishan Pandey
 */
export function isNetherUndefinedNorNull(data: unknown): boolean {
    return !isUndefined(data) && !isNull(data);
}

export const statusProps = (status: string, t: any) => {
    let currentStatus = t(buttonConstant.done);
    let cName = 'bg-success text-green-800 dark:bg-green-900 dark:text-green-300';
    if (status.toLowerCase() === 'pending') {
        currentStatus = t(formConstant.status.pending);
        cName = 'bg-black-400 text-black-800 dark:bg-yellow-900 dark:text-yellow-300';
    }
    return {
        currentStatus,
        cName
    };
};
