import * as React from 'react';

import TextareaAutosize from '@mui/base/TextareaAutosize';
import { TextareaAutosizeProps } from '@mui/material';

const TextArea = React.forwardRef<HTMLTextAreaElement, TextareaAutosizeProps>(({ value, onChange, ...inputProps }, ref) => {
    return (
        <TextareaAutosize
            className="w-full border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-none hover:border-gray-900 p-3 rounded-md !text-black-600 "
            disabled={false}
            ref={ref}
            aria-label="text-area"
            minRows={3}
            value={value}
            placeholder="Your **Markdown** text"
            onChange={onChange}
            {...inputProps}
        />
    );
});

TextArea.displayName = 'TextArea';
export default TextArea;
