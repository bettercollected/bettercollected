'use client';

import { FormField } from '@app/models/dtos/form';
import QuestionWrapper from '@app/views/molecules/ResponderFormFields/QuestionQwrapper';

const VideoField = ({ field, isBuilder = false }: { field: FormField; isBuilder?: boolean }) => {
    const videoUrl = 'https://' + field.attachment?.href?.replace('watch', 'embed');
    return isBuilder ? (
        <iframe src={videoUrl} width="100%" className="aspect-video"></iframe>
    ) : (
        <QuestionWrapper field={field}>
            <iframe src={videoUrl} width="100%" className="aspect-video"></iframe>
        </QuestionWrapper>
    );
};

export default VideoField;
