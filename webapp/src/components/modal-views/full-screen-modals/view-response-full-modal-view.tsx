import EllipsisOption from '@Components/Common/Icons/Common/EllipsisOption';
import { Close } from '@app/components/icons/close';
import { StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { Separator } from '@app/shadcn/components/ui/separator';
import { cn } from '@app/shadcn/util/lib';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteResponseMutation } from '@app/store/workspaces/api';
import { utcToLocalDateTIme } from '@app/utils/dateUtils';
import { getAnswerForField, getTitleForHeader } from '@app/utils/formBuilderBlockUtils';
import DeleteIcon from '@app/views/atoms/Icons/Delete';
import { motion } from 'framer-motion';
import { toast } from 'react-toastify';
import { useFullScreenModal } from '../full-screen-modal-context';

export interface IViewResponseFullModalView {
    response: StandardFormResponseDto;
    formFields: StandardFormFieldDto[];
    formId: string;
    workspaceId: string;
}

const ViewResponseFullModalView = ({ response, formFields, formId, workspaceId }: IViewResponseFullModalView) => {
    const { closeModal } = useFullScreenModal();

    return (
        <motion.div
            initial={{ x: '100%', opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ ease: 'easeInOut', duration: 0.5 }}
            className="h-response-view absolute bottom-0 right-0 flex w-full flex-col overflow-hidden rounded-tl-xl !bg-white md:w-[420px]"
        >
            <div className="flex flex-row justify-between p-4">
                <div className="flex flex-col">
                    <span className="p3-new text-black-800">Response</span>
                    <span className="text-black-500 text-[10px]">{utcToLocalDateTIme(response?.createdAt)}</span>
                </div>
                <div className="flex items-center gap-1">
                    <EllipsisSection formId={formId} workspaceId={workspaceId} responseId={response.responseId} />
                    <Close onClick={closeModal} />
                </div>
            </div>
            <Separator />
            <IndividualFormResponse formFields={formFields} response={response} />
        </motion.div>
    );
};

export const IndividualFormResponse = ({ formFields, response }: { formFields: Array<StandardFormFieldDto>; response: StandardFormResponseDto }) => {
    const form = useAppSelector(selectForm);
    function getTitleForHeaderForTable(field: StandardFormFieldDto) {
        const title = getTitleForHeader(field, form);
        return <span className="p3-new !text-black-800 truncate md:w-[250px]">{title}</span>;
    }
    return (
        <div className="flex min-h-fit w-full flex-col gap-8 overflow-y-auto p-4 pt-6 ">
            {formFields.map((field) => {
                return (
                    <div className="flex flex-col gap-1" key={field.id}>
                        <span className="p4-new text-black-500">{getTitleForHeaderForTable(field)}</span>
                        <span className="p2-new text-black-700">{getAnswerForField(response, field) || '- -'}</span>
                    </div>
                );
            })}
        </div>
    );
};

const EllipsisSection = ({ formId, workspaceId, responseId }: { formId: string; workspaceId: string; responseId: string }) => {
    const [deleteResponse] = useDeleteResponseMutation();
    const { closeModal } = useFullScreenModal();

    const handleDelete = async () => {
        const response: any = await deleteResponse({ workspaceId, formId, responseId });
        if (response?.data) {
            toast('Response Deleted', { type: 'success' });
            closeModal();
        } else {
            toast('Error Deleting Response', { type: 'error' });
        }
    };
    return (
        <Popover>
            <PopoverTrigger>
                <div className="hover:bg-black-200 flex h-fit w-fit items-center justify-center rounded-md p-2">
                    <EllipsisOption className={cn('hidden cursor-pointer')} width={16} height={16} />
                </div>
            </PopoverTrigger>
            <PopoverContent side="left" align="start" className=" !z-[10000]  w-[150px] bg-white p-0 shadow-lg">
                <div className=" p2 !my-2  flex cursor-pointer items-center gap-2 px-4 py-2 !text-red-500 hover:bg-red-50" onClick={handleDelete}>
                    <DeleteIcon className="text-red-500" />
                    Delete
                </div>
            </PopoverContent>
        </Popover>
    );
};

export default ViewResponseFullModalView;
