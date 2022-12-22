import React from 'react';

import { useRouter } from 'next/router';

import styled from '@emotion/styled';
import TextareaAutosize from '@mui/base/TextareaAutosize';
import Checkbox from '@mui/material/Checkbox';
import FormControlLabel from '@mui/material/FormControlLabel';
import MenuItem from '@mui/material/MenuItem';
import Radio from '@mui/material/Radio';
import Select from '@mui/material/Select';
import Slider from '@mui/material/Slider';
import TextField from '@mui/material/TextField';

import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import Loader from '@app/components/ui/loader';
import MarkdownText from '@app/components/ui/markdown-text';
import environments from '@app/configs/environments';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { StandardFormDto, StandardFormQuestionDto } from '@app/models/dtos/form';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';
import { useGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { toEndDottedStr } from '@app/utils/stringUtils';

const StyledTextField = styled.div`
    .MuiInputBase-input {
        padding-left: 0;
        padding-right: 0;
        padding-bottom: 8px;
    }

    .MuiSelect-select {
        padding-right: 32px;
        padding-left: 16px;
        padding-bottom: 16px;
    }

    textarea {
        padding-left: 0;
        padding-right: 0;
        padding-bottom: 8px;
        width: 100%;
        border-bottom-style: dotted;
    }

    textarea:disabled {
        color: rgba(0, 0, 0, 0.38);
    }
`;

interface ISubmission extends IServerSideProps {
    form: StandardFormDto;
}

enum QUESTION_TYPE {
    INPUT_FIELD = 'INPUT_FIELD',
    TEXT_AREA = 'TEXT_AREA',
    VIDEO_CONTENT = 'VIDEO_CONTENT',
    IMAGE_CONTENT = 'IMAGE_CONTENT',
    GROUP_RADIO_QUESTION = 'GROUP_RADIO_QUESTION',
    GROUP_CHECKBOX_QUESTION = 'GROUP_CHECKBOX_QUESTION',
    RADIO = 'RADIO',
    CHECKBOX = 'CHECKBOX',
    DROP_DOWN = 'DROP_DOWN',
    FILE_UPLOAD = 'FILE_UPLOAD',
    LINEAR_SCALE = 'LINEAR_SCALE'
}

export default function Submission({ workspace, submissionId, ...props }: ISubmission) {
    const router = useRouter();
    const breakpoint = useBreakpoint();

    const { isLoading, isError, data } = useGetWorkspaceSubmissionQuery({
        workspace_id: workspace?.id ?? '',
        submission_id: submissionId
    });

    const form: any = data?.payload?.content;

    if (isLoading || isError || !data) return <FullScreenLoader />;

    const getQuestionType = (question: StandardFormQuestionDto) => {
        if (question.isMediaContent && 'video' in question.type) return QUESTION_TYPE.VIDEO_CONTENT;
        if (question.isMediaContent && 'image' in question.type) return QUESTION_TYPE.IMAGE_CONTENT;
        if (question.isGroupQuestion && 'grid' in question.type) {
            if (question.type?.grid?.columns?.type === QUESTION_TYPE.RADIO) return QUESTION_TYPE.GROUP_RADIO_QUESTION;
            if (question.type?.grid?.columns?.type === QUESTION_TYPE.CHECKBOX) return QUESTION_TYPE.GROUP_CHECKBOX_QUESTION;
        }
        if ('paragraph' in question.type && !!question.type.paragraph) return QUESTION_TYPE.TEXT_AREA;
        if ('type' in question.type && question.type.type === QUESTION_TYPE.INPUT_FIELD) return QUESTION_TYPE.INPUT_FIELD;
        if ('type' in question.type && question.type.type === QUESTION_TYPE.DROP_DOWN) return QUESTION_TYPE.DROP_DOWN;
        if ('type' in question.type && question.type.type === QUESTION_TYPE.RADIO) return QUESTION_TYPE.RADIO;
        if ('type' in question.type && question.type.type === QUESTION_TYPE.CHECKBOX) return QUESTION_TYPE.CHECKBOX;
        if ('folderId' in question.type && !!question.type.folderId) return QUESTION_TYPE.FILE_UPLOAD;
        if ('high' in question.type || 'low' in question.type) return QUESTION_TYPE.LINEAR_SCALE;
        return QUESTION_TYPE.INPUT_FIELD;
    };

    const renderGridRowColumns = (question: StandardFormQuestionDto, Component: any) => {
        const gridRowQuestions = question.type?.questions;
        const gridColumnOptions = question.type?.grid?.columns?.options;
        const gridColumnCount = question.type?.grid?.columns?.options && Array.isArray(question.type?.grid?.columns?.options) ? question.type?.grid?.columns?.options.length : 0;
        const gridAnswers = question.answer ? question.answer : [];

        return (
            <div className="">
                <div className={`grid grid-flow-col grid-cols-${gridColumnCount + 1} gap-4`}>
                    <p></p>
                    {gridColumnOptions.map((gcp: any, idx: any) => (
                        <p key={idx} className="font-semibold">
                            {gcp?.value}
                        </p>
                    ))}
                </div>
                {gridRowQuestions.map((grq: any, idx: any) => {
                    return (
                        <div key={idx} className={`grid grid-flow-col grid-cols-${gridColumnCount + 1} gap-4`}>
                            <p className="font-semibold w-fit">{grq?.rowQuestion?.title}</p>
                            {gridColumnOptions.map((gcp: any, idx: any) => {
                                const handleCheckedAnswer = (gcp: any): boolean => {
                                    const questionId = grq?.questionId;
                                    let isSelected = false;
                                    gridAnswers.map((gra: any) => {
                                        if (!!gra?.questionId && gra?.questionId === questionId && gra?.answer && Array.isArray(gra.answer)) {
                                            gra.answer.map((a: any) => {
                                                if (!!a?.value && !!gcp?.value && a?.value === gcp?.value) isSelected = true;
                                            });
                                        }
                                    });
                                    return isSelected;
                                };

                                return (
                                    <div key={idx}>
                                        <Component checked={handleCheckedAnswer(gcp)} />
                                    </div>
                                );
                            })}
                        </div>
                    );
                })}
            </div>
        );
    };

    const renderQuestionTypeField = (question: StandardFormQuestionDto) => {
        const questionType: QUESTION_TYPE = getQuestionType(question);
        switch (questionType) {
            case QUESTION_TYPE.VIDEO_CONTENT:
                const strippedLink = question?.type?.video?.youtubeUri && question?.type?.video?.youtubeUri.split('=').length > 1 ? question?.type?.video?.youtubeUri.split('=')[1] : null;
                const embedUrl = `https://www.youtube.com/embed/${strippedLink}`;

                return (
                    <div className="w-full">
                        {question?.type?.caption && <MarkdownText description={question.type.caption} contentStripLength={1000} markdownClassName="text-base text-grey" textClassName="text-base" />}
                        {question?.type?.video?.youtubeUri && (
                            <div className="mt-3 relative w-full">
                                <iframe src={embedUrl} width="100%" className="min-h-[30vh] xs:min-h-[40vh] md:min-h-[50vh]" frameBorder="0" marginHeight={0} marginWidth={0}>
                                    <Loader />
                                </iframe>
                            </div>
                        )}
                    </div>
                );
            case QUESTION_TYPE.IMAGE_CONTENT:
                if (question?.type?.image?.contentUri)
                    return (
                        <div className="w-full">
                            <img src={question?.type?.image?.contentUri} width="100%" alt={question?.type?.image?.altText} />
                        </div>
                    );
                return <div className="w-full">{question?.type?.image?.altText && <MarkdownText description={question.type.image.altText} contentStripLength={1000} markdownClassName="text-base text-grey" textClassName="text-base" />}</div>;
            case QUESTION_TYPE.GROUP_RADIO_QUESTION:
                return renderGridRowColumns(question, Radio);
            case QUESTION_TYPE.GROUP_CHECKBOX_QUESTION:
                return renderGridRowColumns(question, Checkbox);
            case QUESTION_TYPE.RADIO:
                let radioOptions: any = [];
                if (question.type?.options && Array.isArray(question.type?.options)) {
                    radioOptions = [...question.type?.options];
                }
                const radioAnswers: any = question.answer ? question.answer : [];
                return (
                    <StyledTextField>
                        {radioOptions.map((option: any, idx: any) => (
                            <FormControlLabel key={idx} control={<Radio checked={radioAnswers.includes(option?.value)} />} label={option?.value} />
                        ))}
                    </StyledTextField>
                );
            case QUESTION_TYPE.CHECKBOX:
                let checkboxOptions: any = [];
                if (question.type?.options && Array.isArray(question.type?.options)) {
                    checkboxOptions = [...question.type?.options];
                }
                const checkboxAnswers: any = question.answer ? question.answer : [];
                return (
                    <StyledTextField>
                        {checkboxOptions.map((option: any, idx: any) => (
                            <FormControlLabel key={idx} control={<Checkbox checked={checkboxAnswers.includes(option?.value)} />} label={option?.value} />
                        ))}
                    </StyledTextField>
                );
            case QUESTION_TYPE.TEXT_AREA:
                return (
                    <StyledTextField>
                        <TextareaAutosize value={question.answer} />
                    </StyledTextField>
                );
            case QUESTION_TYPE.DROP_DOWN:
                let dropdownOptions: any = [];
                if (question.type?.options && Array.isArray(question.type?.options)) {
                    dropdownOptions = [...question.type?.options];
                }
                const dropdownAnswers: any = question.answer ? question.answer : [];
                const dropdownAnswer = Array.isArray(dropdownAnswers) && dropdownAnswers.length !== 0 ? dropdownAnswers[0] : 'No answer selected';
                return (
                    <StyledTextField>
                        <Select value={dropdownAnswer}>
                            {dropdownOptions.map((dd: any, idx: any) => (
                                <MenuItem key={idx} value={dd?.value}>
                                    {dd?.value}
                                </MenuItem>
                            ))}
                        </Select>
                    </StyledTextField>
                );
            case QUESTION_TYPE.FILE_UPLOAD:
                return (
                    <Button variant="solid" className="mt-3">
                        Upload File
                        <input type="file" hidden />
                    </Button>
                );
            case QUESTION_TYPE.LINEAR_SCALE:
                const linearScaleLowValue = question.type?.low;
                const linearScaleHightValue = question.type?.high;
                const followerMarks = [];

                for (let i = linearScaleLowValue; i <= linearScaleHightValue; i++) {
                    followerMarks.push({ value: i, label: i });
                }

                const linearScaleAnswers: any = question.answer ? question.answer : [];
                const linearScaleAnswer = Array.isArray(linearScaleAnswers) && linearScaleAnswers.length !== 0 ? Number(linearScaleAnswers[0]) : undefined;

                return <Slider value={linearScaleAnswer} min={linearScaleLowValue} step={1} max={linearScaleHightValue} marks={followerMarks} />;
            case QUESTION_TYPE.INPUT_FIELD:
            default:
                return (
                    <StyledTextField>
                        <TextField value={question.answer} fullWidth variant="standard" />
                    </StyledTextField>
                );
        }
    };

    const goToSubmissions = () => {
        router
            .push(
                {
                    pathname: '/',
                    query: { view: 'mySubmissions' }
                },
                undefined,
                { scroll: true, shallow: true }
            )
            .then((r) => r)
            .catch((e) => e);
    };

    return (
        <div className="relative container mx-auto px-6 md:px-0">
            <div className="!absolute !top-0 !left-0">
                <nav className="flex mt-3 px-6 md:px-0" aria-label="Breadcrumb">
                    <ol className="inline-flex items-center space-x-1 md:space-x-3">
                        <li className="inline-flex items-center">
                            <span aria-hidden onClick={() => router.push('/')} className="cursor-pointer inline-flex items-center text-sm font-medium text-gray-700 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
                                <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z"></path>
                                </svg>
                                Home
                            </span>
                        </li>
                        <li>
                            <div className="flex items-center">
                                <svg className="w-6 h-6 text-gray-400" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                    <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd"></path>
                                </svg>
                                <span aria-hidden onClick={goToSubmissions} className="cursor-pointer ml-1 text-sm font-medium text-gray-700 hover:text-gray-900 md:ml-2 dark:text-gray-400 dark:hover:text-white">
                                    Submissions
                                </span>
                            </div>
                        </li>
                        <li aria-current="page">
                            <div className="flex items-center">
                                <svg className="w-6 h-6 text-gray-400" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                    <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd"></path>
                                </svg>
                                <span className="ml-1 text-sm font-medium text-gray-500 md:ml-2 dark:text-gray-400">{['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.formId, 10) : form.formId}</span>
                            </div>
                        </li>
                    </ol>
                </nav>
            </div>
            <div className="pt-20 pb-14">
                <p className="text-sm text-gray-400 italic">{['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.formId, 30) : form.formId}</p>
                <h1 className="font-semibold text-darkGrey mb-3 text-xl sm:text-2xl md:text-3xl xl:text-4xl 2xl:text-[40px]">{form.title}</h1>
                {form?.description && (
                    <div className="p-6 border-[1.5px] border-gray-200 rounded-lg">
                        <MarkdownText description={form.description} contentStripLength={1000} markdownClassName="text-base text-grey" textClassName="text-base" />
                    </div>
                )}
                <hr className="my-6" />
                {form.questions.map((question: any, idx: any) => (
                    <div key={question?.questionId ?? `${question.formId}_${idx}`} className="p-6 border-[1.5px] border-gray-200 rounded-lg mb-4">
                        {/* <p className="font-semibold text-xs underline underline-offset-4 decoration-gray-200 text-gray-400">Question #{idx}</p> */}
                        <h1 className="font-semibold text-lg text-gray-600">{question.title}</h1>
                        {question?.description && <MarkdownText description={question.description} contentStripLength={1000} markdownClassName="text-base text-grey" textClassName="text-base" />}
                        {renderQuestionTypeField(question)}
                    </div>
                ))}
            </div>
        </div>
    );
}

export async function getServerSideProps(_context: any) {
    const globalProps = (await getGlobalServerSidePropsByDomain(_context)).props;
    let form: StandardFormDto | null = null;
    const { cookies } = _context.req;
    const submissionId = _context.query.id;

    const hasCustomDomain = !_context.req.headers.host === environments.CLIENT_HOST;

    if (!hasCustomDomain) {
        return {
            redirect: {
                permanent: false,
                destination: '/'
            }
        };
    }

    const auth = !!cookies.Authorization ? `Authorization=${cookies.Authorization}` : '';
    const refresh = !!cookies.RefreshToken ? `RefreshToken=${cookies.RefreshToken}` : '';

    const config = {
        method: 'GET',
        headers: {
            cookie: `${auth};${refresh}`
        }
    };

    try {
        if (globalProps.hasCustomDomain && globalProps.workspaceId) {
            const formResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${globalProps.workspaceId}/submissions/${submissionId}`, config).catch((e) => e);
            form = (await formResponse?.json().catch((e: any) => e))?.payload?.content ?? null;
        }
    } catch (err) {
        form = null;
        console.error(err);
    }

    return {
        props: {
            ...globalProps,
            form,
            submissionId
        }
    };
}
