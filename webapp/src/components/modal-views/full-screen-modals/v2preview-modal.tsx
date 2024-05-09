import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import BackButton from '@app/views/molecules/FormBuilder/BackButton';
import PreviewWrapper from '@app/views/molecules/FormBuilder/PreviewWrapper';
import Form from '@app/views/organism/Form/Form';
import { useFullScreenModal } from '../full-screen-modal-context';

export const PreviewFullModalView = () => {
    const { resetResponderState } = useResponderState();
    const { resetFormResponseAnswer } = useFormResponse();
    const handleResetResponderState = () => {
        resetResponderState();
        resetFormResponseAnswer();
    };
    const { closeModal } = useFullScreenModal();
    return (
        <div className="relative h-full w-full">
            <div className="absolute left-4 top-3 z-50 " onClick={closeModal}>
                <BackButton hideForSmallScreen />
            </div>
            <PreviewWrapper handleResetResponderState={handleResetResponderState}>
                <Form isPreviewMode />
            </PreviewWrapper>
        </div>
    );
};
