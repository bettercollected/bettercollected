import React from 'react';

import BottomSheetModalWrapper from '@Components/Modals/ModalWrappers/BottomSheetModalWrapper';
import cn from 'classnames';

import SelectGroup from '@app/components/group/select-group';
import { Close } from '@app/components/icons/close';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';

const SelectGroupFullModalView = () => {
    return (
        <BottomSheetModalWrapper>
            <SelectGroup />
        </BottomSheetModalWrapper>
    );
};
export default SelectGroupFullModalView;
