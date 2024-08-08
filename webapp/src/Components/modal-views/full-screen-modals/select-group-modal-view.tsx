import React from 'react';

import BottomSheetModalWrapper from '@Components/Modals/ModalWrappers/BottomSheetModalWrapper';

import SelectGroup from '@app/Components/group/select-group';


const SelectGroupFullModalView = () => {
    return (
        <BottomSheetModalWrapper>
            <SelectGroup />
        </BottomSheetModalWrapper>
    );
};
export default SelectGroupFullModalView;