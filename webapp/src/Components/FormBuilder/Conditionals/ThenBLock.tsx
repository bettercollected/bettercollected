import React from 'react';

import { ConditionalActions, IFormFieldState } from '@app/store/form-builder/types';

const ThenBlock = ({ field, action }: { field: IFormFieldState; action: ConditionalActions }) => {
    return (
        <div className={'flex flex-col gap-2 p-4 bg-new-white-200 rounded-lg'}>
            <h1 className={'text-pink-500 text-sm'}>THEN</h1>
            <div className={'flex flex-row gap-2 '}>
                {/*<ConditionalListDropDown firstState={{ value: 'State' }} allState={People} />*/}
                {/*<ConditionalListDropDown size={'small'} firstState={{ value: 'Select a Field' }} allState={Comparisons} />*/}
            </div>
        </div>
    );
};

export default ThenBlock;
