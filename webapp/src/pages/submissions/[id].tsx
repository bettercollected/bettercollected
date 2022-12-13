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
import globalServerProps from '@app/lib/serverSideProps';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';

interface ISubmission extends IServerSideProps {}

export default function Submission(props: ISubmission) {
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
    console.log(globalProps);
    console.log(_context.query);
    return {
        props: {
            ...globalProps
        }
    };
}
