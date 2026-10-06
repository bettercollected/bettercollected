import ModalCloseButton from '@app/components/modal-views/modal-close-button';
import { FieldTypes, StaffFeedback, StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { Separator } from '@app/shadcn/components/ui/separator';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { useModal } from '@app/components/modal-views/context';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { utcToLocalDateTIme } from '@app/utils/date-utils';
import { downloadFile } from '@app/utils/file-utils';
import { resolvePipesInTitle, titleHasPipes } from '@app/utils/answer-piping';
import { getAnswerForField, getTitleForHeader } from '@app/utils/form-builder-block-utils';
import { getInternalFields } from '@app/utils/internal-fields';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import InternalFieldsPanel from '@Components/form/internal-fields-panel';
import RespondentFeedbackPanel from '@Components/form/respondent-feedback-panel';
import { getGroupChildren, getGroupItems, getItemHeader, isRepeatingGroup, itemScopeAnswers } from '@app/utils/repeating-groups';
import { getItemAnswer } from '@app/utils/response-export';
import DeleteIcon from '@Components/icons/delete';
import { motion } from 'framer-motion';
import { MoreVertical } from 'lucide-react';
import { useFullScreenModal } from '../full-screen-modal-context';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@app/shadcn/components/ui/table';

interface IViewResponseFullModalView {
    response: StandardFormResponseDto;
    formFields: StandardFormFieldDto[];
    // The form the response belongs to. Without it the body falls back to the
    // redux form — empty or stale outside a form page (e.g. the workspace
    // deletion-requests table), which blanked question titles and pipes.
    form?: StandardFormDto;
    formId: string;
    workspaceId: string;
    // The form's current internal ("office use") fields, from the submission
    // endpoint (members only). Falls back to the ones on `form`.
    internalFields?: StandardFormFieldDto[];
    // The team's updates to the respondent (members only), from the same
    // endpoint; the form's settings say whether posting is on.
    feedback?: StaffFeedback | null;
}

const ViewResponseFullModalView = ({ response, formFields, form, formId, workspaceId, internalFields, feedback }: IViewResponseFullModalView) => {
    const staffFields = internalFields ?? getInternalFields(form);
    const { toast } = useToast();
    const { closeModal } = useFullScreenModal();

    return (
        <motion.div
            {...({
                initial: { x: '100%', opacity: 0 },
                animate: { x: 0, opacity: 1 },
                transition: { ease: 'easeInOut', duration: 0.5 },
                className: 'h-response-view absolute bottom-0 right-0 flex w-full flex-col overflow-hidden rounded-tl-xl !bg-white md:w-[420px]'
            } as any)}
        >
            <div className="flex flex-row justify-between p-4">
                <div className="flex flex-col">
                    <span className="p3-new text-black-800">Response</span>
                    <span className="text-black-600 text-[10px]">{utcToLocalDateTIme(response?.createdAt)}</span>
                </div>
                <div className="flex items-center gap-1">
                    <EllipsisSection formId={formId} workspaceId={workspaceId} responseId={response.responseId} />
                    <ModalCloseButton onClick={closeModal} className="h-8 w-8" iconClassName="h-6 w-6" />
                </div>
            </div>
            <Separator />
            <div className="h-[90vh] overflow-y-auto">
                <IndividualFormResponse formFields={formFields} response={response} form={form} />
                {feedback && (
                    <div className="px-4 pb-4">
                        <RespondentFeedbackPanel
                            key={response.responseId}
                            workspaceId={workspaceId}
                            formId={formId}
                            responseId={response.responseId}
                            feedback={feedback}
                            enabled={!!form?.settings?.respondentFeedbackEnabled}
                            statuses={form?.settings?.feedbackStatuses ?? []}
                        />
                    </div>
                )}
                {staffFields.length > 0 && (
                    <div className="px-4 pb-8">
                        <InternalFieldsPanel key={response.responseId} fields={staffFields} response={response} formId={formId} workspaceId={workspaceId} />
                    </div>
                )}
            </div>
        </motion.div>
    );
};

export const IndividualFormResponse = ({ formFields, response, form, className }: { formFields: Array<StandardFormFieldDto>; response: StandardFormResponseDto; form?: StandardFormDto; className?: string }) => {

    const { toast } = useToast();

    const reduxForm = useAppSelector(selectForm);
    const standardForm = form ? form : reduxForm;
    // Questions may pipe earlier answers ("Hello @name…") — resolve them with
    // THIS submission's answers so the question reads exactly as the responder
    // saw it, instead of showing raw builder pipe labels.
    const pipeContext = {
        slides: standardForm?.fields,
        answers: response?.answers ?? {},
        hiddenValues: (response as any)?.hiddenFields ?? {}
    };
    function getTitleForHeaderForTable(field: StandardFormFieldDto) {
        const resolvedField = titleHasPipes(field?.title) ? ({ ...field, title: resolvePipesInTitle(field.title, pipeContext) } as StandardFormFieldDto) : field;
        const title = getTitleForHeader(resolvedField, standardForm);

        // The question is the label; the answer is the content. Muted medium
        // label over full-size ink answer keeps the two unmistakable.
        return <span className="text-black-600 text-[13px] font-medium leading-snug">{title}</span>;
    }
    const downloadFormFile = async (ans: any) => {
        try {
            if (!ans?.file_metadata?.url) return;
            downloadFile(ans?.file_metadata?.url, ans?.file_metadata.name ?? ans?.file_metadata.id);
        } catch (err) {
            toast({ description: 'Error downloading file', variant: 'destructive' });
        }
    };
    return (
        <div className={cn('flex w-full flex-col gap-8 p-4 pt-6', className)}>
            {formFields.map((field) => {
                const ans = response.answers[field.id];

                if (isRepeatingGroup(field)) {
                    // One card per item, each with that item's answers.
                    const items = getGroupItems(response.answers, field.id);
                    const children = getGroupChildren(field).filter((child) => child.type !== FieldTypes.TEXT);
                    return (
                        <div className="flex flex-col gap-2" key={field.id}>
                            {getTitleForHeaderForTable(field)}
                            {items.length === 0 && <span className="text-black-600 text-sm italic">No answer</span>}
                            {items.map((item, index) => {
                                const itemContext = { ...pipeContext, answers: itemScopeAnswers(response.answers, { groupId: field.id, index, childIds: children.map((c) => c.id) }) };
                                return (
                                    <section key={index} className="border-black-300 flex flex-col gap-3 rounded-lg border bg-white p-3" aria-label={getItemHeader(field, index, pipeContext)}>
                                        <span className="text-black-800 text-[13px] font-semibold">{getItemHeader(field, index, pipeContext)}</span>
                                        {children.map((child) => {
                                            const answerText = getItemAnswer(item, child);
                                            const childTitle = getTitleForHeader(titleHasPipes(child.title) ? ({ ...child, title: resolvePipesInTitle(child.title, itemContext) } as StandardFormFieldDto) : child, standardForm);
                                            return (
                                                <div className="flex flex-col gap-1" key={child.id}>
                                                    <span className="text-black-600 text-[13px] font-medium leading-snug">{childTitle}</span>
                                                    {answerText !== '' ? <span className="text-black-900 text-base leading-relaxed">{answerText}</span> : <span className="text-black-600 text-sm italic">No answer</span>}
                                                </div>
                                            );
                                        })}
                                    </section>
                                );
                            })}
                        </div>
                    );
                }

                if (field.type === FieldTypes.TABULAR_INPUT) {
                    const rowTitles = field.properties?.rowTitles;
                    const colTitles = field.properties?.columnTitles || [];
                    const tabularData = ans?.tabular_value || [];

                    return (
                        <div className="flex flex-col gap-2" key={field.id}>
                            {getTitleForHeaderForTable(field)}
                            <div className="overflow-x-auto rounded-md border border-gray-200">
                                <Table className="min-w-full text-xs">
                                    <TableHeader>
                                        <TableRow className="bg-gray-50">
                                            <TableHead className="w-24 border-r"></TableHead>
                                            {colTitles.map((col, i) => (
                                                <TableHead key={i} className="text-center font-bold border-r last:border-r-0">
                                                    {col}
                                                </TableHead>
                                            ))}
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {rowTitles?.map((rowTitle, rIdx) => (
                                            <TableRow key={rIdx}>
                                                <TableCell className="bg-gray-50 font-bold border-r text-center">{rowTitle}</TableCell>
                                                {colTitles.map((_, cIdx) => (
                                                    <TableCell key={cIdx} className="text-center border-r last:border-r-0">
                                                        {tabularData[rIdx]?.[cIdx] || '-'}
                                                    </TableCell>
                                                ))}
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        </div>
                    );
                }

                if (field.type === FieldTypes.FILE_UPLOAD || field.type === FieldTypes.INPUT_FILE_UPLOAD) {
                    return (
                        <div className="flex flex-col gap-1.5" key={field.id}>
                            {getTitleForHeaderForTable(field)}
                            {ans?.file_metadata ? (
                                <div onClick={() => downloadFormFile(ans)} className={cn('!text-black-600 p2-new w-[140px] truncate rounded px-2 py-1', ans?.file_metadata?.url ? 'bg-black-300 active:bg-black-400 cursor-pointer' : 'cursor-default')}>
                                    {getAnswerForField(response, field)}
                                </div>
                            ) : (
                                <span className="text-black-600 text-sm italic">No answer</span>
                            )}
                        </div>
                    );
                }
                const answerText = getAnswerForField(response, field);
                return (
                    <div className="flex flex-col gap-1.5" key={field.id}>
                        {getTitleForHeaderForTable(field)}
                        {answerText ? <span className="text-black-900 text-base leading-relaxed">{answerText}</span> : <span className="text-black-600 text-sm italic">No answer</span>}
                    </div>
                );
            })}
            {response.hiddenFields && Object.keys(response.hiddenFields).length > 0 && (
                <div className="flex flex-col gap-3 border-t pt-4">
                    <span className="p4-new text-black-600">Hidden fields (from the share link)</span>
                    {Object.entries(response.hiddenFields).map(([name, value]) => (
                        <div className="flex flex-col gap-1" key={name}>
                            <span className="p4-new text-black-600 font-mono">{name}</span>
                            <span className="p2-new text-black-700">{value}</span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

const EllipsisSection = ({ formId, workspaceId, responseId }: { formId: string; workspaceId: string; responseId: string }) => {
    const { closeModal } = useFullScreenModal();
    const { openModal: openConfirmModal } = useModal();
    const workspace = useAppSelector(selectWorkspace);
    const { can } = useWorkspacePermissions();

    // Deleting is permanent, so it goes through the DELETE_RESPONSE confirm.
    // Only one modal layer renders at a time (full-screen wins), so the drawer
    // closes before the confirmation opens.
    const handleDelete = () => {
        closeModal();
        openConfirmModal('DELETE_RESPONSE', { workspace, formId, responseId });
    };
    // the menu's only action is response.delete (Editors and up)
    if (!can(WorkspacePermission.RESPONSE_DELETE)) return null;
    return (
        <Popover>
            <PopoverTrigger>
                <div className="hover:bg-black-200 flex h-fit w-fit items-center justify-center rounded-md p-2">
                    <MoreVertical className={cn('cursor-pointer')} width={16} height={16} />
                </div>
            </PopoverTrigger>
            <PopoverContent side="left" align="start" className="w-[180px] bg-white p-0 shadow-lg">
                <div className=" p2 !my-2  flex cursor-pointer items-center gap-2 px-4 py-2 !text-[#C43D3D] hover:bg-[#FBEFEF]" onClick={handleDelete}>
                    <DeleteIcon className="text-[#C43D3D]" />
                    Delete response
                </div>
            </PopoverContent>
        </Popover>
    );
};

export default ViewResponseFullModalView;
