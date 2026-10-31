'use client';

import { CSSProperties, ReactNode } from 'react';

import Image from 'next/image';

import { StarIcon } from '@Components/icons/start';
import { format } from 'date-fns';
import { nl as dutch } from 'date-fns/locale/nl';
import parse from 'html-react-parser';
import { Check, ChevronDown, Download } from 'lucide-react';

import { FormTheme } from '@app/constants/theme';
import { FieldTypes, StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { PipeContext, resolvePipesInText, resolvePipesInTitle, stringTitleToDoc } from '@app/utils/answer-piping';
import { calculatedAnswerValue, formatCalculatedValue, isShownToRespondents } from '@app/utils/calculated-fields';
import { LogicSources, getHiddenFieldIds } from '@app/utils/conditional-logic';
import { formatAmount } from '@app/utils/currency';
import { isoToLocalDate } from '@app/utils/date-rules';
import { formatFileSizeMb } from '@app/utils/file-utils';
import { firstPartyImageProps } from '@app/utils/first-party-image';
import { DISPLAY_LIST_SEPARATOR, getAnswerForField } from '@app/utils/form-builder-block-utils';
import { legacyTitleText } from '@app/utils/legacy-title';
import { getGroupChildren, getGroupItems, getItemHeader, getItemHiddenChildIds, isRepeatingGroup, itemScopeAnswers } from '@app/utils/repeating-groups';
import { answered, choiceRows, fieldHasAnswer } from '@app/utils/response-page';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/get-html-from-json';
import { HEADING_CLASSES, TEXT_BLOCK_BODY_CLASSES } from '@app/utils/text-headings';
import { ChoiceContent, choiceRowStyle } from '@app/views/atoms/choice';
import { scaleCellStyle } from '@app/views/molecules/responder-form-fields/linear-rating';
import { themed } from '@app/views/molecules/theme/theme-root';
import { softInk, styleTokens } from '@app/views/molecules/theme/theme-shared';

export const UNREADABLE_SHORT = 'Could not be decrypted';
export const NO_ANSWER = 'No answer';
export const NOT_SHOWN = 'Not shown to the respondent';
export const ANSWERED_THEN_SKIPPED = 'Answered, then skipped';

/** What every question of the page needs to draw itself, from the form and this response. */
export interface ReadOnlyContext {
    form: StandardFormDto;
    theme: FormTheme;
    pipe: PipeContext;
    sources: LogicSources;
    /** The response's answers could not be decrypted: a blank means "unreadable", never "no answer". */
    unreadable: boolean;
    /** Marks the author's text with the form's language when it differs from the page's. */
    lang?: string;
    /** The language dates and numbers are written in, as the respondent's form writes them. */
    formatLanguage: 'en' | 'nl';
    /** The n.m numbers of the page's questions, when the form numbers them. */
    numbers?: Record<string, string>;
    onDownload: (file: { url?: string; name?: string; id?: string }) => void;
}

const INK_ON_WHITE = '#101828';

/** A question's title as the respondent read it: pipes resolved with this response's answers. */
function titleHtml(field: StandardFormFieldDto, pipe: PipeContext): string {
    const legacy = legacyTitleText(field);
    const stringTitle = typeof field?.title === 'string' && field.title ? field.title : legacy;
    // a plain-string title goes through the editor's schema as text, never as raw HTML
    const title = stringTitle ? stringTitleToDoc(stringTitle, [{ type: 'bold' }]) : field?.title;
    return getHtmlFromJson(resolvePipesInTitle(title, pipe)) ?? '';
}

const hasVisibleText = (html: string) => /(^|>)[^<]*\S/.test(html);

const NoAnswer = ({ ctx }: { ctx: ReadOnlyContext }) => (
    <p className="text-[15px] italic" style={{ color: softInk(ctx.theme) }} data-no-answer>
        {ctx.unreadable ? UNREADABLE_SHORT : NO_ANSWER}
    </p>
);

/** The name of a control: the question's title, or a plain "Answer" for an untitled question. */
const nameProps = (labelledBy?: string) => (labelledBy ? { 'aria-labelledby': labelledBy } : { 'aria-label': 'Answer' });

/** A read-only box: the answer in the form's field shape, exposed as a read-only text box. */
function ReadOnlyBox({ labelledBy, multiline = false, children, trailing }: { labelledBy?: string; multiline?: boolean; children: ReactNode; trailing?: ReactNode }) {
    return (
        <div
            role="textbox"
            aria-readonly="true"
            aria-multiline={multiline || undefined}
            {...nameProps(labelledBy)}
            className={cn('flex min-h-12 w-full items-center justify-between gap-3 border px-4 py-3 text-base leading-snug [overflow-wrap:anywhere]', multiline && 'items-start')}
            style={{ background: '#ffffff', color: INK_ON_WHITE, borderColor: 'var(--rp-edge)', borderRadius: 'var(--rp-field-radius)', whiteSpace: multiline ? 'pre-wrap' : undefined }}
        >
            <span className="min-w-0 flex-1">{children}</span>
            {trailing}
        </div>
    );
}

/** The options of a choice question, then a quiet "No answer" when none is marked. */
function ChoiceAnswer({ rows, multiple, labelledBy, ctx }: { rows: Array<{ key: string; label: string; selected: boolean }>; multiple: boolean; labelledBy?: string; ctx: ReadOnlyContext }) {
    return (
        <>
            <OptionRows rows={rows} multiple={multiple} labelledBy={labelledBy} ctx={ctx} />
            {!rows.some((row) => row.selected) && <NoAnswer ctx={ctx} />}
        </>
    );
}

/** Every option listed, the chosen ones marked by the control's shape and by `aria-checked`. */
function OptionRows({ rows, multiple, labelledBy, ctx }: { rows: Array<{ key: string; label: string; selected: boolean }>; multiple: boolean; labelledBy?: string; ctx: ReadOnlyContext }) {
    const tokens = styleTokens(ctx.theme.style);
    return (
        <div role={multiple ? 'group' : 'radiogroup'} aria-readonly={multiple ? undefined : true} {...nameProps(labelledBy)} className={cn('flex w-full flex-col', !tokens.ruledChoices && 'gap-2')}>
            {rows.map((row) => {
                const style = choiceRowStyle(ctx.theme, row.selected);
                return (
                    <div
                        key={row.key}
                        role={multiple ? 'checkbox' : 'radio'}
                        aria-checked={row.selected}
                        aria-readonly={multiple ? true : undefined}
                        data-chosen={row.selected || undefined}
                        // a read-only row: no pointer, and the hover edge of a live option stays off
                        className={cn(style.className, 'cursor-default hover:border-(--choice-edge)')}
                        style={style.style}
                    >
                        <ChoiceContent kind={multiple ? 'checkbox' : 'radio'} selected={row.selected} theme={ctx.theme} solid={style.solid}>
                            {row.label}
                        </ChoiceContent>
                    </div>
                );
            })}
        </div>
    );
}

function RatingMarks({ field, answer, labelledBy, ctx }: { field: StandardFormFieldDto; answer: any; labelledBy?: string; ctx: ReadOnlyContext }) {
    const steps = field.properties?.steps || 5;
    const value = typeof answer?.number === 'number' ? answer.number : 0;
    return (
        <div className="flex w-fit flex-col gap-1">
            <div role="radiogroup" aria-readonly="true" {...nameProps(labelledBy)} className="flex flex-wrap gap-1">
                {Array.from({ length: steps }, (_, index) => index + 1).map((step) => (
                    <span key={step} role="radio" aria-checked={step === value} aria-label={`${step} of ${steps}`} className="flex h-12 w-12 items-center justify-center">
                        <StarIcon width={40} height={39} fill={step <= value ? ctx.theme.secondary : 'transparent'} stroke={ctx.theme.secondary} aria-hidden="true" />
                    </span>
                ))}
            </div>
            <p className="flex items-center gap-1.5 text-[13px] tabular-nums" style={{ color: ctx.theme.primary }}>
                <Check className="h-4 w-4 shrink-0" strokeWidth={2.5} style={{ color: themed('--form-highlight-edge', ctx.theme.secondary) }} aria-hidden="true" />
                {`Rated ${value} of ${steps}`}
            </p>
        </div>
    );
}

function ScaleMarks({ field, answer, labelledBy, ctx }: { field: StandardFormFieldDto; answer: any; labelledBy?: string; ctx: ReadOnlyContext }) {
    const tokens = styleTokens(ctx.theme.style);
    const start = field.properties?.startFrom ?? 1;
    const end = +(field.properties?.steps ?? 10);
    const value = typeof answer?.number === 'number' ? answer.number : undefined;
    const values = Array.from({ length: Math.max(0, end - start + 1) }, (_, index) => start + index);
    return (
        <div role="radiogroup" aria-readonly="true" {...nameProps(labelledBy)} className="flex flex-row flex-wrap gap-2">
            {values.map((step) => {
                const selected = step === value;
                return (
                    <span
                        key={step}
                        role="radio"
                        aria-checked={selected}
                        style={scaleCellStyle(ctx.theme, selected, tokens.cardRadius) as CSSProperties}
                        className={cn('relative flex h-12 w-12 items-center justify-center border border-(--scale-edge) text-base tabular-nums', selected ? 'font-semibold' : 'font-normal')}
                    >
                        <span>{step}</span>
                        {selected && <Check aria-hidden="true" className="absolute top-0.5 right-0.5 h-2.5 w-2.5" strokeWidth={3} />}
                    </span>
                );
            })}
        </div>
    );
}

function TableBox({ children, labelledBy }: { children: ReactNode; labelledBy?: string }) {
    // wide tables scroll inside their own box, never the page
    return (
        <div className="max-w-full overflow-x-auto border" style={{ borderColor: 'var(--rp-edge)', borderRadius: 'var(--rp-field-radius)', background: '#ffffff', color: INK_ON_WHITE }} tabIndex={0} role="region" {...nameProps(labelledBy)}>
            {children}
        </div>
    );
}

function TabularAnswer({ field, answer, labelledBy }: { field: StandardFormFieldDto; answer: any; labelledBy?: string }) {
    const rowTitles: string[] = field.properties?.rowTitles ?? [];
    const columnTitles: string[] = field.properties?.columnTitles ?? [];
    const values: string[][] = Array.isArray(answer?.tabular_value) ? answer.tabular_value : [];
    return (
        <TableBox labelledBy={labelledBy}>
            <table className="min-w-full border-collapse text-sm">
                <thead>
                    <tr>
                        <td className="w-24 border-r border-b p-2" style={{ borderColor: 'var(--rp-rule)' }} />
                        {columnTitles.map((title, index) => (
                            <th key={index} scope="col" className="border-r border-b p-2 text-center font-semibold last:border-r-0" style={{ borderColor: 'var(--rp-rule)' }}>
                                {title}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rowTitles.map((rowTitle, rowIndex) => (
                        <tr key={rowIndex}>
                            <th scope="row" className="border-r border-b p-2 text-center font-semibold" style={{ borderColor: 'var(--rp-rule)' }}>
                                {rowTitle}
                            </th>
                            {columnTitles.map((_, columnIndex) => (
                                <td key={columnIndex} className="border-r border-b p-2 text-center last:border-r-0" style={{ borderColor: 'var(--rp-rule)' }}>
                                    {values[rowIndex]?.[columnIndex] || '-'}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </TableBox>
    );
}

function MatrixAnswer({ field, answers, labelledBy, ctx }: { field: StandardFormFieldDto; answers: Record<string, any>; labelledBy?: string; ctx: ReadOnlyContext }) {
    const rows = field.properties?.fields ?? [];
    const columns = rows[0]?.properties?.choices ?? [];
    const multiple = !!field.properties?.allowMultipleSelection;
    return (
        <TableBox labelledBy={labelledBy}>
            <table className="min-w-full border-collapse text-sm">
                <thead>
                    <tr>
                        <td className="border-r border-b p-2" style={{ borderColor: 'var(--rp-rule)' }} />
                        {columns.map((column, index) => (
                            <th key={column.id ?? index} scope="col" className="border-r border-b p-2 text-center font-semibold last:border-r-0" style={{ borderColor: 'var(--rp-rule)' }}>
                                {column.value || `Column ${index + 1}`}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row, rowIndex) => {
                        const answer = answers[row.id];
                        const chosen: string[] = multiple ? (answer?.choices?.values ?? []) : answer?.choice?.value ? [answer.choice.value] : [];
                        return (
                            <tr key={row.id ?? rowIndex}>
                                <th scope="row" className="border-r border-b p-2 text-left font-semibold" style={{ borderColor: 'var(--rp-rule)' }}>
                                    {row.title?.toString() || `Row ${rowIndex + 1}`}
                                </th>
                                {(row.properties?.choices ?? []).map((choice: any, index: number) => {
                                    const selected = chosen.includes(choice.id);
                                    return (
                                        <td key={choice.id ?? index} className="border-r border-b p-2 last:border-r-0" style={{ borderColor: 'var(--rp-rule)' }}>
                                            <span className="flex justify-center">
                                                <MatrixMark selected={selected} multiple={multiple} theme={ctx.theme} />
                                                <span className="sr-only">{selected ? 'Selected' : 'Not selected'}</span>
                                            </span>
                                        </td>
                                    );
                                })}
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </TableBox>
    );
}

/** The marked or empty control of one matrix cell (decorative: the cell says it in words). */
function MatrixMark({ selected, multiple, theme }: { selected: boolean; multiple: boolean; theme: FormTheme }) {
    const on = themed('--form-highlight-edge', theme.secondary);
    return (
        <span aria-hidden="true" className={cn('flex h-5 w-5 items-center justify-center border-2', multiple ? 'rounded-[4px]' : 'rounded-full')} style={{ borderColor: selected ? on : theme.tertiary, background: selected && multiple ? on : '#ffffff' }}>
            {selected && (multiple ? <Check className="h-3.5 w-3.5" strokeWidth={3} style={{ color: '#ffffff' }} /> : <span className="h-2.5 w-2.5 rounded-full" style={{ background: on }} />)}
        </span>
    );
}

function FileAnswer({ answer, labelledBy, ctx }: { answer: any; labelledBy?: string; ctx: ReadOnlyContext }) {
    const file = answer?.file_metadata;
    const size = formatFileSizeMb(file?.size);
    // the server's short-lived signed link is the only way to the file
    if (!file?.url) {
        return (
            <ReadOnlyBox labelledBy={labelledBy}>
                {file?.name ?? file?.id}
                {size && <span className="ml-2 text-sm opacity-70">{size}</span>}
            </ReadOnlyBox>
        );
    }
    return (
        <>
            <button
                type="button"
                aria-describedby={labelledBy}
                onClick={() => ctx.onDownload({ url: file.url, name: file.name, id: file.id })}
                className="flex min-h-12 w-fit max-w-full items-center gap-2 border px-4 py-3 text-left text-base font-medium print:hidden"
                style={{ background: '#ffffff', color: INK_ON_WHITE, borderColor: 'var(--rp-edge)', borderRadius: 'var(--rp-field-radius)' }}
            >
                <Download className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="min-w-0 [overflow-wrap:anywhere]">
                    Download <span className="font-semibold">{file.name ?? file.id}</span>
                </span>
                {size && <span className="shrink-0 text-sm opacity-70">{size}</span>}
            </button>
            {/* on paper the button is gone: the file's name (and size) stand in for it */}
            <p className="hidden text-base print:block" data-print-file>
                {`File: ${file.name ?? file.id}${size ? ` (${size})` : ''}`}
            </p>
        </>
    );
}

/** The date as the form shows it ("30 October 2026", "30 oktober 2026"), or the stored text when it is not a date. */
function dateText(value: string, language: 'en' | 'nl'): string {
    const date = isoToLocalDate(value);
    return date ? format(date, 'PPP', { locale: language === 'nl' ? dutch : undefined }) : value;
}

const present = (value: unknown) => value !== undefined && value !== null && value !== '';

/** The answer control of one question, read-only. Null: a block with no answer to show. */
function AnswerBody({ field, answers, labelledBy, ctx }: { field: StandardFormFieldDto; answers: Record<string, any>; labelledBy?: string; ctx: ReadOnlyContext }) {
    const answer = answers[field.id];
    // the server emptied what it could not decrypt: say so, never list options or "No answer"
    if (ctx.unreadable) return <NoAnswer ctx={ctx} />;
    const value = getAnswerForField({ answers } as any, field, DISPLAY_LIST_SEPARATOR);
    switch (field.type) {
        case FieldTypes.MULTIPLE_CHOICE: {
            const multiple = !!field.properties?.allowMultipleSelection;
            // an unanswered question lists its options too, none marked
            return <ChoiceAnswer rows={choiceRows(field, answer, multiple)} multiple={multiple} labelledBy={labelledBy} ctx={ctx} />;
        }
        case FieldTypes.YES_NO: {
            const rows = [
                { key: 'yes', label: 'Yes', selected: answer?.boolean === true },
                { key: 'no', label: 'No', selected: answer?.boolean === false }
            ];
            return <ChoiceAnswer rows={rows} multiple={false} labelledBy={labelledBy} ctx={ctx} />;
        }
        case FieldTypes.DROP_DOWN: {
            const chosen = choiceRows(field, answer, !!field.properties?.allowMultipleSelection).filter((row) => row.selected);
            if (chosen.length === 0) return <NoAnswer ctx={ctx} />;
            return (
                <ReadOnlyBox labelledBy={labelledBy} trailing={<ChevronDown className="h-4 w-4 shrink-0 opacity-60" aria-hidden="true" />}>
                    {chosen.map((row) => row.label).join(', ')}
                </ReadOnlyBox>
            );
        }
        case FieldTypes.RATING:
            return answered(answer) ? <RatingMarks field={field} answer={answer} labelledBy={labelledBy} ctx={ctx} /> : <NoAnswer ctx={ctx} />;
        case FieldTypes.LINEAR_RATING:
            return answered(answer) ? <ScaleMarks field={field} answer={answer} labelledBy={labelledBy} ctx={ctx} /> : <NoAnswer ctx={ctx} />;
        case FieldTypes.FILE_UPLOAD:
        case FieldTypes.INPUT_FILE_UPLOAD:
            return answer?.file_metadata ? <FileAnswer answer={answer} labelledBy={labelledBy} ctx={ctx} /> : <NoAnswer ctx={ctx} />;
        case FieldTypes.TABULAR_INPUT:
            return answered(answer) ? <TabularAnswer field={field} answer={answer} labelledBy={labelledBy} /> : <NoAnswer ctx={ctx} />;
        case FieldTypes.MATRIX:
            return (field.properties?.fields ?? []).some((row) => answered(answers[row.id])) ? <MatrixAnswer field={field} answers={answers} labelledBy={labelledBy} ctx={ctx} /> : <NoAnswer ctx={ctx} />;
        case FieldTypes.CALCULATED: {
            const calculated = calculatedAnswerValue(answer);
            if (calculated === null) return <NoAnswer ctx={ctx} />;
            return <ReadOnlyBox labelledBy={labelledBy}>{typeof calculated === 'boolean' ? (calculated ? 'Yes' : 'No') : formatCalculatedValue(calculated, field.properties?.format, ctx.formatLanguage)}</ReadOnlyBox>;
        }
        case FieldTypes.DATE:
        case FieldTypes.DAY:
            return present(value) ? <ReadOnlyBox labelledBy={labelledBy}>{dateText(String(value), ctx.formatLanguage)}</ReadOnlyBox> : <NoAnswer ctx={ctx} />;
        case FieldTypes.CURRENCY: {
            // the amount as the form shows it ("€ 12,50"), not the export's "EUR 12.50"
            const amount = formatAmount(answer?.currency, ctx.formatLanguage);
            return amount ? <ReadOnlyBox labelledBy={labelledBy}>{amount}</ReadOnlyBox> : <NoAnswer ctx={ctx} />;
        }
        case FieldTypes.LONG_TEXT:
            return present(value) ? (
                <ReadOnlyBox labelledBy={labelledBy} multiline>
                    {String(value)}
                </ReadOnlyBox>
            ) : (
                <NoAnswer ctx={ctx} />
            );
        default:
            return present(value) ? <ReadOnlyBox labelledBy={labelledBy}>{String(value)}</ReadOnlyBox> : <NoAnswer ctx={ctx} />;
    }
}

/** A question the form did not show this respondent (a logic rule hid it): its title and why there is no answer. */
function NotShownQuestion({ field, ctx, idPrefix }: { field: StandardFormFieldDto; ctx: ReadOnlyContext; idPrefix: string }) {
    const html = titleHtml(field, ctx.pipe);
    const titleId = `${idPrefix}title-${field.id}`;
    return (
        <div role="group" aria-labelledby={titleId} data-question data-not-shown className="flex flex-col gap-1 opacity-80" id={`${idPrefix}${field.id}`}>
            <div id={titleId} className="text-[15px] font-medium [&_p]:inline" style={{ color: softInk(ctx.theme) }} lang={ctx.lang}>
                {hasVisibleText(html) ? parse(html) : null}
            </div>
            <p className="text-[13px] italic" style={{ color: softInk(ctx.theme) }}>
                {NOT_SHOWN}
            </p>
        </div>
    );
}

function ReadOnlyImage({ href, alt }: { href?: string; alt?: string }) {
    if (!href) return null;
    return (
        <div className="relative my-2 w-full">
            <Image style={{ objectFit: 'contain', width: 'fit-content', maxWidth: '100%', maxHeight: '240px' }} sizes="100vw" {...firstPartyImageProps(href)} alt={alt ?? ''} height={0} width={0} />
        </div>
    );
}

/**
 * One question as the form draws it, read-only: the title as the respondent
 * read it (pipes resolved with their answers), the description, then every
 * option or the answer, marked. `answers` is the map the question's answer
 * lives in (the response's, or one repeating-group item's).
 */
export function ReadOnlyQuestion({ field, answers, ctx, idPrefix = 'rp-', note }: { field: StandardFormFieldDto; answers: Record<string, any>; ctx: ReadOnlyContext; idPrefix?: string; note?: string }) {
    const tokens = styleTokens(ctx.theme.style);
    const html = titleHtml(field, ctx.pipe);
    const titleId = `${idPrefix}title-${field.id}`;
    const descriptionId = `${idPrefix}desc-${field.id}`;
    const description = resolvePipesInText(field.description, ctx.pipe);
    const whyWeAsk = field.properties?.whyWeAsk?.trim();

    if (field.type === FieldTypes.IMAGE_CONTENT) return <ReadOnlyImage href={field.attachment?.href} alt={field.attachment?.properties?.description} />;
    if (field.type === FieldTypes.VIDEO_CONTENT) return null;
    // content, not a question: statements and headings, and a group that does not repeat (the form shows only its heading)
    if (isContent(field)) {
        return (
            <div className={cn(TEXT_BLOCK_BODY_CLASSES, 'form-text-block', HEADING_CLASSES)} style={{ color: ctx.theme.primary }} lang={ctx.lang} id={`${idPrefix}${field.id}`} data-content>
                {parse(html)}
                {field.type === FieldTypes.GROUP && description && (
                    <p className="mt-1.5 text-[15px] leading-relaxed" style={{ color: softInk(ctx.theme) }}>
                        {description}
                    </p>
                )}
            </div>
        );
    }

    const isGroup = isRepeatingGroup(field);
    const number = ctx.numbers?.[field.id];
    const hasTitle = hasVisibleText(html);
    const keptFromRespondents = field.type === FieldTypes.CALCULATED && !isShownToRespondents(field);

    return (
        <div
            role="group"
            aria-labelledby={hasTitle ? titleId : undefined}
            aria-describedby={[description ? descriptionId : null, whyWeAsk ? `${idPrefix}why-${field.id}` : null].filter(Boolean).join(' ') || undefined}
            data-question
            id={`${idPrefix}${field.id}`}
            className={cn('flex flex-col gap-1 lg:gap-2', tokens.divider && 'border-b pb-7')}
            style={tokens.divider ? { borderColor: (ctx.theme.tertiary ?? '#818CA0') + '40' } : undefined}
        >
            <div className="flex items-baseline gap-2.5">
                {number && (
                    <span aria-hidden="true" data-testid="question-number" className="shrink-0 text-[16px] leading-[1.4] font-semibold tabular-nums" style={{ color: ctx.theme.primary }}>
                        {number}
                    </span>
                )}
                <div className="min-w-0">
                    <div id={titleId} className={cn(tokens.labelClass, 'form-title-face [&_p]:inline', HEADING_CLASSES)} style={{ color: ctx.theme.primary }} lang={ctx.lang}>
                        {hasTitle ? parse(html) : null}
                    </div>
                    {description && (
                        <div id={descriptionId} className="mt-1.5 max-w-[62ch] text-[15px] leading-relaxed" style={{ color: softInk(ctx.theme) }} lang={ctx.lang}>
                            {description}
                        </div>
                    )}
                    {whyWeAsk && (
                        <p id={`${idPrefix}why-${field.id}`} className="mt-2 max-w-[62ch] border-l-2 pl-3 text-[14px] leading-relaxed" style={{ borderColor: themed('--form-highlight-rule', ctx.theme.tertiary), color: softInk(ctx.theme) }} lang={ctx.lang}>
                            <span className="font-semibold">Why we ask this</span> {whyWeAsk}
                        </p>
                    )}
                </div>
            </div>
            {note && (
                <p className="text-[13px] font-medium italic" style={{ color: softInk(ctx.theme) }} data-question-note>
                    {note}
                </p>
            )}
            {keptFromRespondents && (
                <p className="text-[13px] italic" style={{ color: softInk(ctx.theme) }}>
                    Calculated for staff; kept from the respondent.
                </p>
            )}
            <ReadOnlyImage href={field.imageUrl} />
            {isGroup ? (
                <RepeatingGroupAnswer field={field} answers={answers} ctx={ctx} labelledBy={hasTitle ? titleId : undefined} idPrefix={idPrefix} />
            ) : (
                <AnswerBody field={field} answers={answers} labelledBy={hasTitle ? titleId : undefined} ctx={ctx} />
            )}
        </div>
    );
}

function RepeatingGroupAnswer({ field, answers, ctx, labelledBy, idPrefix }: { field: StandardFormFieldDto; answers: Record<string, any>; ctx: ReadOnlyContext; labelledBy?: string; idPrefix: string }) {
    const items = getGroupItems(answers, field.id);
    const children = getGroupChildren(field).filter((child) => child.type !== FieldTypes.TEXT);
    if (items.length === 0) return <NoAnswer ctx={ctx} />;
    return (
        <div className="flex flex-col gap-3" role="list" aria-labelledby={labelledBy}>
            {items.map((item, index) => {
                const header = getItemHeader(field, index, { ...ctx.pipe, answers });
                const hidden = getItemHiddenChildIds(field, answers, index, ctx.sources);
                // pipes inside an item read that item's answers
                const itemAnswers = itemScopeAnswers(answers, { groupId: field.id, index, childIds: children.map((child) => child.id) });
                const itemCtx: ReadOnlyContext = { ...ctx, numbers: undefined, pipe: { ...ctx.pipe, answers: itemAnswers } };
                return (
                    <div key={index} role="listitem" aria-label={header} data-group-item className="flex flex-col gap-5 border bg-white p-4" style={{ borderColor: 'var(--rp-edge)', borderRadius: 'var(--rp-card-radius)', color: INK_ON_WHITE }}>
                        <h3 className="text-[15px] font-semibold">{header}</h3>
                        {children.map((child) =>
                            hidden.has(child.id) && !answered(item[child.id]) ? (
                                <NotShownQuestion key={child.id} field={child} ctx={itemCtx} idPrefix={`${idPrefix}i${index}-`} />
                            ) : (
                                <ReadOnlyQuestion key={child.id} field={child} answers={item} ctx={itemCtx} idPrefix={`${idPrefix}i${index}-`} />
                            )
                        )}
                    </div>
                );
            })}
        </div>
    );
}

/** Content the form shows, not a question: text and statements, pictures, videos, a group that does not repeat. */
export function isContent(field: StandardFormFieldDto): boolean {
    return field.type === FieldTypes.TEXT || field.type === FieldTypes.STATEMENT || field.type === FieldTypes.IMAGE_CONTENT || field.type === FieldTypes.VIDEO_CONTENT || (field.type === FieldTypes.GROUP && !isRepeatingGroup(field));
}

/** The fields of a page shown to the respondent and the ones a logic rule hid, in the form's order. */
export function pageQuestions(fields: StandardFormFieldDto[], answers: Record<string, any>, sources: LogicSources) {
    const hidden = getHiddenFieldIds(fields, answers, sources);
    // a hidden question that still holds an answer is shown with it: the data was collected
    const notShown = (field: StandardFormFieldDto) => hidden.has(field.id) && !fieldHasAnswer(field, answers);
    return fields.map((field) => ({ field, notShown: notShown(field) }));
}

export { NotShownQuestion };
