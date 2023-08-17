import _ from 'lodash';

import { atom, useAtom } from 'jotai';

import { GlobalQueryTagTypes } from '@app/models/enums/rtkQueryTags';

interface RefetchCallback {
    (): void;
}

const refetchAtom = atom({});

export function useRefetchQuery() {
    const [refetchQueries, setRefetchQueries] = useAtom(refetchAtom);

    const addRefetch = (queryTagType: GlobalQueryTagTypes, refetch: RefetchCallback) => {
        if (!(queryTagType in refetchQueries)) {
            setRefetchQueries({ ...refetchQueries, ...{ [queryTagType]: refetch } });
        }
    };

    const invalidateTags = (queryTagTypes: [GlobalQueryTagTypes]) => {
        /**
         * It invalidates the
         * @param {Array} queryTagTypes
         */
        queryTagTypes.map((queryTagType) => {
            if (!_.isEmpty(refetchAtom) && queryTagType in refetchQueries) {
                //@ts-ignore
                refetchQueries[queryTagType]();
            }
        });

        return () => {};
    };

    return { addRefetch, invalidateTags };
}
