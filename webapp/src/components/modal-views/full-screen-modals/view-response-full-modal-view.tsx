import { Close } from '@app/components/icons/close';
import { Separator } from '@app/shadcn/components/ui/separator';
import { useFullScreenModal } from '../full-screen-modal-context';
import { StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { getAnswerForField } from '@app/utils/formBuilderBlockUtils';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/getHtmlFromJson';
import { utcToLocalDateTIme } from '@app/utils/dateUtils';
import { motion } from 'framer-motion';

export interface IViewResponseFullModalView {
    response: StandardFormResponseDto;
    formFields: StandardFormFieldDto[];
}

const ViewResponseFullModalView = ({ response, formFields }: IViewResponseFullModalView) => {
    const { closeModal } = useFullScreenModal();

    return (
        <motion.div initial={{ x: '100%', opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ ease: 'easeInOut', duration: 0.5 }} className="h-response-view absolute bottom-0 right-0 flex w-[420px] flex-col overflow-hidden rounded-tl-xl !bg-white">
            <div className="flex flex-row justify-between p-4">
                <div className="flex flex-col">
                    <span className="p3-new text-black-800">Response</span>
                    <span className="text-black-500 text-[10px]">{utcToLocalDateTIme(response?.createdAt)}</span>
                </div>
                <Close onClick={closeModal} />
            </div>
            <Separator />
            <div className="min-h-calc-68 flex flex-col gap-8 overflow-y-auto p-4 pt-6 ">
                {formFields.map((field) => {
                    return (
                        <div className="flex flex-col gap-1" key={field.id}>
                            <span className="p4-new text-black-500">{extractTextfromJSON(field)}</span>
                            <span className="p2-new text-black-700">{getAnswerForField(response, field) || '- -'}</span>
                        </div>
                    );
                })}
            </div>
        </motion.div>
    );
};

export default ViewResponseFullModalView;
