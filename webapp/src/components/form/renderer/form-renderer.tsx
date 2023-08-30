import React from 'react';

import BetterCollectedForm from '@Components/Form/BetterCollectedForm';
import LongText from '@Components/Form/LongText';
import styled from '@emotion/styled';
import Checkbox from '@mui/material/Checkbox';
import FormControlLabel from '@mui/material/FormControlLabel';
import MenuItem from '@mui/material/MenuItem';
import Radio from '@mui/material/Radio';
import Rating from '@mui/material/Rating';
import TextField from '@mui/material/TextField';
import {AdapterDayjs} from '@mui/x-date-pickers/AdapterDayjs';
import {DatePicker} from '@mui/x-date-pickers/DatePicker';
import {LocalizationProvider} from '@mui/x-date-pickers/LocalizationProvider';

import BetterInput from '@app/components/Common/input';
import SelectDropdown from '@app/components/dropdown/select';
import Button from '@app/components/ui/button';
import Loader from '@app/components/ui/loader';
import {StandardFormFieldDto} from '@app/models/dtos/form';
import {selectInvalidFields} from '@app/store/fill-form/slice';
import {useAppSelector} from '@app/store/hooks';

const StyledTextField = styled.div`
  textarea:disabled {
    color: rgba(0, 0, 0, 0.38);
  }
`;

export enum QUESTION_TYPE {
    DATE = 'date',
    EMAIL = 'email',
    SHORT_TEXT = 'short_text',
    LONG_TEXT = 'long_text',
    MULTIPLE_CHOICE = 'multiple_choice',
    OPINION_SCALE = 'opinion_scale',
    RANKING = 'ranking',
    RATING = 'rating',
    DROP_DOWN = 'dropdown',
    MATRIX = 'matrix',
    FILE_UPLOAD = 'file_upload',
    GROUP = 'group',
    PAYMENT = 'payment',
    STATEMENT = 'statement',
    VIDEO_CONTENT = 'VIDEO_CONTENT',
    IMAGE_CONTENT = 'IMAGE_CONTENT',
    DATE_INPUT = 'date_input',
    EMAIL_INPUT = 'email_input',
    SHORT_TEXT_INPUT = 'short_text_input',
    LONG_TEXT_INPUT = 'long_text_input',
    MULTIPLE_CHOICE_INPUT = 'multiple_choice_input',
    RANKING_INPUT = 'ranking_input',
    RATING_INPUT = 'rating_input',
    DROP_DOWN_INPUT = 'drop_down_input',
    MEDIA_INPUT = 'media_input',
    MATRIX_ROW_INPUT = 'matrix_row_input'
}

enum AttachmentType {
    IMAGE = 'image',
    VIDEO = 'video'
}

enum VideoEmbedProvider {
    YOUTUBE = 'youtube',
    VIMEO = 'vimeo'
}

//TODO: fetch the data using api slice and set the form...
// you will need two api calls conditionally based on questions or responses.
interface FormRendererProps {
    form: any;
    response?: any;
    enabled?: boolean;
    preview?: boolean
}

FormRenderer.defaultProps = {
    enabled: false
};

export default function FormRenderer({form, response, enabled, preview = false}: FormRendererProps) {

    const renderGridRowColumns = (question: any) => {
        const gridRowQuestions = question.properties?.fields;
        const gridColumnOptions = question.properties?.fields[0].properties.choices;
        const Component = gridRowQuestions[0].properties.allow_multiple_selection ? Checkbox : Radio;

        const gridColumnCount = gridColumnOptions && Array.isArray(gridColumnOptions) ? gridColumnOptions.length : 0;
        const gridAnswers = question.answer ? question.answer : [];

        return (
            <div className="" data-testid="form-renderer">
                <div className={`grid grid-flow-col grid-cols-${gridColumnCount + 1} gap-4`}>
                    <p></p>
                    {gridColumnOptions.map((gcp: any, idx: any) => (
                        <p key={idx} className="font-semibold">
                            {gcp?.label}
                        </p>
                    ))}
                </div>
                {gridRowQuestions.map((grq: any, idx: any) => {
                    const ans = response?.answers[grq.id];
                    let ansChoices: any;
                    if (grq.properties?.allow_multiple_selection) {
                        ansChoices = ans?.choices && Array.isArray(ans?.choices?.values) ? ans?.choices?.values : [];
                    } else {
                        ansChoices = ans?.choice?.value ? [ans?.choice?.value] : [];
                    }

                    return (
                        <div key={idx} className={`grid grid-flow-col grid-cols-${gridColumnCount + 1} gap-4`}>
                            <p className="font-semibold w-fit">{grq?.title}</p>
                            {gridColumnOptions.map((gcp: any, idx: any) => {
                                const handleCheckedAnswer = (gcp: any) => {
                                    return ansChoices.includes(gcp?.label);
                                };

                                return (
                                    <div key={idx}>
                                        <Component checked={handleCheckedAnswer(gcp)}/>
                                    </div>
                                );
                            })}
                        </div>
                    );
                })}
            </div>
        );
    };

    function renderYoutubeVideo(youtubeUri: string, description?: string) {
        const splitUriByEquals = youtubeUri.split('=');
        const strippedLink = splitUriByEquals.length > 1 ? splitUriByEquals[1] : null;
        const embedUrl = `https://www.youtube.com/embed/${strippedLink}`;
        return (
            <div className="w-full">
                {description && <div>{description}</div>}
                {strippedLink && (
                    <div className="relative w-full aspect-video">
                        <iframe src={embedUrl} width="100%" className="aspect-video" frameBorder="0" marginHeight={0}
                                marginWidth={0}>
                            <Loader/>
                        </iframe>
                    </div>
                )}
            </div>
        );
    }

    const renderQuestionTypeField = (question: StandardFormFieldDto, ans?: any, response?: any) => {
        const questionType: QUESTION_TYPE = question.type;
        switch (questionType) {
            case QUESTION_TYPE.DATE:
                const date_format = question.properties?.date_format ?? 'MM/DD/YYYY';
                const answer = ans?.date ?? '';
                return (
                    <LocalizationProvider dateAdapter={AdapterDayjs}>
                        <DatePicker label="" renderInput={(params) => <TextField {...params} />} onChange={(e) => {
                        }} inputFormat={date_format} value={answer} disabled={true}/>
                    </LocalizationProvider>
                );
            case QUESTION_TYPE.LONG_TEXT:
                return <LongText field={question} ans={ans} enabled={enabled}/>;
            case QUESTION_TYPE.MULTIPLE_CHOICE:
                const choiceAnswer = ans?.choice?.value ?? ans?.choices?.values;
                return (
                    <StyledTextField>
                        {question.properties.choices?.map((option: any, idx: number) => (
                            <div key={idx} className="flex items-center gap-3">
                                {option?.attachment?.href &&
                                    <img width={80} height={80} src={option?.attachment?.href}/>}
                                <FormControlLabel control={question.properties?.allow_multiple_selection ?
                                    <Checkbox checked={choiceAnswer?.includes(option?.label)}/> :
                                    <Radio checked={option?.label == choiceAnswer}/>} label={option?.label}/>
                            </div>
                        ))}
                    </StyledTextField>
                );
            case QUESTION_TYPE.OPINION_SCALE:
                const selected_answer: any = ans?.number;
                const start_form = question?.properties?.start_form;
                let steps = question?.properties?.steps;
                steps = start_form != 0 ? steps + 1 : steps;
                const numberBoxes = [];
                for (let i = 0; i < steps; i++) {
                    if (i >= start_form)
                        numberBoxes.push(
                            <span key={i}
                                  className={`border border-gray-900 rounded mx-1 px-2 py-1 ${selected_answer !== undefined && selected_answer === i ? 'bg-gray-900 text-gray-200' : 'bg-gray-200 text-gray-900'}`}>
                                {i}
                            </span>
                        );
                }
                return <StyledTextField className="mt-2">{numberBoxes}</StyledTextField>;

            case QUESTION_TYPE.RANKING:
                if (ans) {
                    return (
                        <>
                            {ans?.choices?.values?.map((answer: any, idx: number) => {
                                return (
                                    <div key={idx} className="p-3 mt-3 mb-3 rounded-md border-[1px] border-gray-300">
                                        <span className="ml-2">
                                            {idx + 1}. {answer}
                                        </span>
                                    </div>
                                );
                            })}
                        </>
                    );
                } else {
                    const choices = question?.properties?.choices ?? [];
                    const choicesArray: Array<number> = [];
                    for (let i = 0; i < choices.length; i++) {
                        choicesArray.push(i + 1);
                    }
                    return (
                        <>
                            {choices.map((choice: any, idx: number) => {
                                return (
                                    <div key={idx} className="p-3 mt-3 mb-3 rounded">
                                        <SelectDropdown value={''} className="h-6" disabled>
                                            {choicesArray.map((dd: number) => (
                                                <MenuItem key={dd} value={''}>
                                                    {dd}
                                                </MenuItem>
                                            ))}
                                        </SelectDropdown>
                                        <span className="ml-2">{choice.label}</span>
                                    </div>
                                );
                            })}
                        </>
                    );
                }

            case QUESTION_TYPE.RATING:
                return <Rating name="size-large" size="large" defaultValue={ans?.number || 0} precision={1}
                               max={!!question.properties.steps ? parseInt(question.properties.steps) : 3} readOnly/>;

            case QUESTION_TYPE.DROP_DOWN:
                let dropdownOptions: any = [];
                if (question.properties?.choices && Array.isArray(question.properties?.choices)) {
                    dropdownOptions = [...question.properties?.choices];
                }
                return (
                    <StyledTextField>
                        <SelectDropdown value={ans?.text} fullWidth disabled={ans}>
                            {dropdownOptions.map((dd: any, idx: any) => (
                                <MenuItem disabled key={idx} value={dd?.label}>
                                    {dd?.label}
                                </MenuItem>
                            ))}
                        </SelectDropdown>
                    </StyledTextField>
                );

            case QUESTION_TYPE.MATRIX:
                return renderGridRowColumns(question);
            case QUESTION_TYPE.FILE_UPLOAD:
                return (
                    <Button variant="solid" size="medium" className="mt-3">
                        Upload File
                        <BetterInput type="file" hidden/>
                    </Button>
                );
            case QUESTION_TYPE.GROUP:
                return (
                    <>
                        {question.properties.fields.map((question: any, idx: number) => (
                            <div className="my-5" key={idx}>
                                {renderQuestionField(question, response)}
                            </div>
                        ))}
                    </>
                );

            case QUESTION_TYPE.STATEMENT:
                // Render no input element for statement
                return <></>;
            case QUESTION_TYPE.SHORT_TEXT:
                return <BetterInput
                    value={ans?.text || ans?.email || ans?.number || ans?.boolean || ans?.url || ans?.file_url || ans?.payment?.name}
                    disabled/>;
            case QUESTION_TYPE.EMAIL:
                return <BetterInput
                    value={ans?.text || ans?.email || ans?.number || ans?.boolean || ans?.url || ans?.file_url || ans?.payment?.name}
                    disabled/>;
            default:
                return <></>;
        }
    };

    function renderVimeoVideo(href: string) {
        const match = href.match(/https:\/\/vimeo\.com\/(\d+)/);
        if (match) {
            const videoId = match[1];
            return <iframe width="100%" height="550" className="aspect-video"
                           src={`https://player.vimeo.com/video/${videoId}`} allow="autoplay; encrypted-media"/>;
        } else {
            return <a href={href}>Click here to see video attachment.</a>;
        }
    }

    function renderVideoSource(href: string) {
        return (
            <div className="mt-2">
                <p className="text-gray-400">Couldn&apos;t display. Unsupported media type.</p>
                <a className="text-blue-500 mt-1" rel="noreferrer" target="_blank" href={href}>
                    Click here to see video attachment.
                </a>
            </div>
        );
    }

    function renderQuestionAttachment(attachment: any) {
        switch (attachment.type) {
            case AttachmentType.IMAGE:
                return <img className="min-h-[200px]" src={attachment.href} alt={attachment.properties?.description}/>;
            case AttachmentType.VIDEO:
                if (attachment?.href == null) break;
                const embed_provider = attachment.embed_provider;
                if (embed_provider == VideoEmbedProvider.YOUTUBE) return renderYoutubeVideo(attachment.href);
                else if (embed_provider == VideoEmbedProvider.VIMEO) return renderVimeoVideo(attachment.href);
                else return renderVideoSource(attachment.href);
            default:
                break;
        }
        return <p className="text-gray-300">Couldn&apos;t display media Unsupported Type.</p>;
    }

    const renderQuestionField = (question: StandardFormFieldDto, response?: any) => (
        <div className="flex flex-col gap-3">
            <h1 className="body1 !text-black-900">{question.title}</h1>
            {/* {question?.description && <MarkdownText description={question.description} contentStripLength={1000} markdownClassName="body4" textClassName="body4" />} */}
            {question.attachment?.type && renderQuestionAttachment(question.attachment)}
            {renderQuestionTypeField(question, response ? response[question.id || ''] : undefined, response)}
        </div>
    );

    return (
        <div data-testid="form-renderer" className="relative max-w-[700px] w-full  md:px-0">
            {form?.settings?.provider === 'self' ? (
                <BetterCollectedForm form={form} response={response} enabled={enabled} isPreview={preview}/>
            ) : (
                <div className="flex flex-col gap-4">
                    <div className="p-6 bg-white rounded-lg flex flex-col gap-4">
                        <h1 className="font-semibold h4">{form?.title}</h1>
                        {/* {form?.description && <MarkdownText description={form?.description} contentStripLength={1000} markdownClassName="body4" textClassName="body4" />} */}
                    </div>
                    {form?.fields?.map((question: StandardFormFieldDto, idx: number) => {
                        return (
                            <div key={question?.id + idx}
                                 className={`p-6 bg-white relative rounded-lg border border-solid`}>
                                {question?.validations?.required &&
                                    <div className="absolute top-5 right-5 text-red-500">*</div>}
                                {renderQuestionField(question, response?.answers)}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
