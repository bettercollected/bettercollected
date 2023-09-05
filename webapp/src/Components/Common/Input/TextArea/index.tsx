import * as React from 'react';

import TextareaAutosize from '@mui/base/TextareaAutosize';
import { TextareaAutosizeProps } from '@mui/material';

const TextArea = React.forwardRef<HTMLTextAreaElement, TextareaAutosizeProps>(({ value, onChange, ...inputProps }, ref) => {
    return <TextareaAutosize className="w-full rounded-md border-black-300 p-3  !text-black-800 placeholder:text-black-400 " disabled={false} ref={ref} aria-label="text-area" minRows={3} value={value} onChange={onChange} {...inputProps} />;
});

TextArea.displayName = 'TextArea';
export default TextArea;
