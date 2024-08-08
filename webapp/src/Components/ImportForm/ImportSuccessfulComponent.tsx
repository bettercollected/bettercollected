import React, { useCallback, useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/legacy/image';

import { debounce } from 'lodash';

import CircularCheck from '@Components/Common/Icons/Common/CircularCheck';
import CopyIcon from '@Components/Common/Icons/Common/Copy';
import ProLogo from '@Components/Common/Icons/Common/ProLogo';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import { CircularProgress } from '@mui/material';
import { AnimatePresence, motion } from 'framer-motion';
import ContentEditable from 'react-contenteditable';
import { toast } from 'react-toastify';

import GoogleFolder from '@app/assets/images/google_folder.png';
import { Close } from '@app/Components/icons/close';
import TickIcon from '@app/Components/icons/tick-icon';
import { useModal } from '@app/Components/modal-views/context';
import { useFullScreenModal } from '@app/Components/modal-views/full-screen-modal-context';
import environments from '@app/configs/environments';
import { toastMessage } from '@app/constants/locales/toast-message';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { StandardFormDto } from '@app/models/dtos/form';
import { selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import GreenCheckedCircle from '@app/views/atoms/Icons/GreenCheckedCircle';

export default function ImportSuccessfulComponent({ form }: { form: StandardFormDto }) {
    return (
        <div className="flex w-full flex-col items-center px-5 pb-5 pt-5 lg:w-[867px] lg:px-12 lg:pt-10">
            <GreenCheckedCircle />
            <div className="h3-new mt-6 !text-[#7248BC]"> {form?.title}</div>
            <div className="h3-new">Imported Successfully!</div>
            <div className="p4-new text-black-700">now appearing more beautiful</div>
            <div className="mb-6 mt-12 flex flex-row items-center gap-2">
                <CircularProgress size={16} />
                <span>Opening</span>
            </div>
        </div>
    );
}
