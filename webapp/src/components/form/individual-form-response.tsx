import { FieldTypes, StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { downloadFile } from '@app/utils/file-utils';
import { resolvePipesInTitle, titleHasPipes } from '@app/utils/answer-piping';
import { DISPLAY_LIST_SEPARATOR, getAnswerForField, getTitleForHeader } from '@app/utils/form-builder-block-utils';
import { getGroupChildren, getGroupItems, getItemHeader, isRepeatingGroup, itemScopeAnswers } from '@app/utils/repeating-groups';
import { getItemAnswer } from '@app/utils/response-export';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@app/shadcn/components/ui/table';

/** The stored parts of a response that could not be decrypted, in words. */
export const UNREADABLE_LABELS: Record<string, string> = { answers: 'answers', hidden_fields: 'hidden fields', internal_answers: 'staff fields' };
export const UNREADABLE_MESSAGE = 'This response could not be decrypted';
// per question, when the notice above already says why
export const UNREADABLE_SHORT = 'Could not be decrypted';

/** Said once at the top of a response whose stored data did not decrypt; per question the text stays short. */
export const UnreadableNotice = ({ unreadable }: { unreadable: string[] }) => {
    if (unreadable.length === 0) return null;
    const answersUnreadable = unreadable.includes('answers');
    return (
        <div className="rounded border border-[#E8C7C7] bg-[#FBEFEF] p-3 text-sm text-[#8A2D2D]" data-unreadable-notice>
            <p className="font-medium">{answersUnreadable ? UNREADABLE_MESSAGE : 'Some data in this response could not be decrypted'}</p>
            <p className="mt-1">The stored data is not readable ({unreadable.map((name) => UNREADABLE_LABELS[name] ?? name).join(', ')}). It is not shown as empty answers.</p>
        </div>
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
    // The server empties what it cannot decrypt and names it here; a blank
    // answer then means "could not be read", never "no answer".
    const unreadable = response?.unreadableFields ?? [];
    const answersUnreadable = unreadable.includes('answers');
    const noAnswer = <span className="text-black-600 text-sm italic">{answersUnreadable ? UNREADABLE_SHORT : 'No answer'}</span>;
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
            await downloadFile(ans?.file_metadata?.url, ans?.file_metadata.name ?? ans?.file_metadata.id);
        } catch (err) {
            toast({ description: 'Error downloading file', variant: 'destructive' });
        }
    };
    return (
        <div className={cn('flex w-full flex-col gap-8 p-4 pt-6', className)}>
            <UnreadableNotice unreadable={unreadable} />
            {formFields.map((field) => {
                const ans = response.answers[field.id];

                if (isRepeatingGroup(field)) {
                    // One card per item, each with that item's answers.
                    const items = getGroupItems(response.answers, field.id);
                    const children = getGroupChildren(field).filter((child) => child.type !== FieldTypes.TEXT);
                    return (
                        <div className="flex flex-col gap-2" key={field.id}>
                            {getTitleForHeaderForTable(field)}
                            {items.length === 0 && noAnswer}
                            {items.map((item, index) => {
                                const itemContext = { ...pipeContext, answers: itemScopeAnswers(response.answers, { groupId: field.id, index, childIds: children.map((c) => c.id) }) };
                                return (
                                    <section key={index} className="border-black-300 flex flex-col gap-3 rounded border bg-white p-3" aria-label={getItemHeader(field, index, pipeContext)}>
                                        <span className="text-black-800 text-[13px] font-semibold">{getItemHeader(field, index, pipeContext)}</span>
                                        {children.map((child) => {
                                            const answerText = getItemAnswer(item, child, DISPLAY_LIST_SEPARATOR);
                                            const childTitle = getTitleForHeader(titleHasPipes(child.title) ? ({ ...child, title: resolvePipesInTitle(child.title, itemContext) } as StandardFormFieldDto) : child, standardForm);
                                            return (
                                                <div className="flex flex-col gap-1" key={child.id}>
                                                    <span className="text-black-600 text-[13px] font-medium leading-snug">{childTitle}</span>
                                                    {answerText !== '' ? <span className="text-black-900 text-base leading-relaxed">{answerText}</span> : noAnswer}
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
                                <div onClick={() => downloadFormFile(ans)} className={cn('text-black-600! p2-new w-[140px] truncate rounded px-2 py-1', ans?.file_metadata?.url ? 'bg-black-300 active:bg-black-400 cursor-pointer' : 'cursor-default')}>
                                    {getAnswerForField(response, field, DISPLAY_LIST_SEPARATOR)}
                                </div>
                            ) : (
                                noAnswer
                            )}
                        </div>
                    );
                }
                const answerText = getAnswerForField(response, field, DISPLAY_LIST_SEPARATOR);
                return (
                    <div className="flex flex-col gap-1.5" key={field.id}>
                        {getTitleForHeaderForTable(field)}
                        {answerText ? <span className="text-black-900 text-base leading-relaxed">{answerText}</span> : noAnswer}
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
