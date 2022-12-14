import Checkboxes from '@app/components/form-components/checkboxes';
import DatePickerRenderer from '@app/components/form-components/date-picker';
import Description from '@app/components/form-components/description';
import Dropdown from '@app/components/form-components/dropdown';
import FileUpload from '@app/components/form-components/file-upload';
import Heading from '@app/components/form-components/heading';
import LinearScale from '@app/components/form-components/linear-scale';
import MultipleCheckboxGrid from '@app/components/form-components/multiple-checkbox-grid';
import MultipleChoiceGrid from '@app/components/form-components/multiple-choice-grid';
import RadioButton from '@app/components/form-components/radio-button';
import ShortAnswer from '@app/components/form-components/short-answer';
import TextInput from '@app/components/form-components/text-input';
import TextArea from '@app/components/form-components/textarea';
import environments from '@app/configs/environments';
import globalServerProps from '@app/lib/serverSideProps';
import { StandardFormDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';

interface ISubmission extends IServerSideProps {
    form: StandardFormDto;
    submission: StandardFormResponseDto;
}

export default function Submission({ form, submission, ...props }: ISubmission) {
    console.log(form, submission);
    return (
        <div className="p-10 w-full">
            <div className={'w-[900px] mx-auto'}>
                <Heading>Welcome to Form Renderer</Heading>
                <Description>This is a sample description of the topic</Description>
                <Checkboxes />
                <Dropdown />
                <TextArea />
                <FileUpload />
                <TextInput title="Text Input" />
                <RadioButton />
                <LinearScale />
                <ShortAnswer />
                <DatePickerRenderer />
                <MultipleChoiceGrid />
                <MultipleCheckboxGrid />
            </div>
        </div>
    );
}

export async function getServerSideProps(_context: any) {
    const globalProps = (await globalServerProps(_context)).props;
    const { cookies } = _context.req;
    const workspaceId = _context.query.workspaceId;
    const formCustomUrl = _context.query.formCustomUrl;
    const formId = _context.query.formId;
    const submissionId = _context.query.id;
    let form: StandardFormDto | null = null;
    let submission: StandardFormResponseDto | null = null;

    const auth = !!cookies.Authorization ? `Authorization=${cookies.Authorization}` : '';
    const refresh = !!cookies.RefreshToken ? `RefreshToken=${cookies.RefreshToken}` : '';

    const config = {
        method: 'GET',
        headers: {
            cookie: `${auth};${refresh}`
        }
    };

    try {
        const formResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${workspaceId}/forms/${formCustomUrl}`, config).catch((e) => e);
        form = (await formResponse?.json().catch((e: any) => e))?.payload?.content ?? null;

        const formSubmission = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${workspaceId}/forms/${formId}/submissions/${submissionId}`, config).catch((e) => e);
        submission = (await formSubmission?.json().catch((e: any) => e))?.payload?.content ?? null;
    } catch (err) {
        form = null;
        console.error(err);
    }

    return {
        props: {
            ...globalProps,
            form,
            submission
        }
    };
}
