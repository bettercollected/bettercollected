import React, { useEffect, useState } from 'react';

import { Button, Dialog, DialogContent, DialogContentText, DialogProps, DialogTitle, useMediaQuery, useTheme } from '@mui/material';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Absolute imports
import { toEndDottedStr } from '@app/utils/stringUtils';

type Props = {
    scrollTitle?: string;
    description: string;
    contentStripLength?: number;
    displayShowMore?: boolean;
    markdownClassName?: string;
    textClassName?: string;
    onClick: any;
};

MarkdownText.defaultProps = {
    scrollTitle: '',
    contentStripLength: 110,
    displayShowMore: true,
    markdownClassName: '',
    textClassName: '',
    onClick: () => {}
};
export default function MarkdownText({ description, scrollTitle = '', onClick = () => {}, contentStripLength = 110, displayShowMore = true, markdownClassName = '', textClassName = '' }: Props) {
    const [showDesc, setShowDesc] = useState('');
    const [open, setOpen] = React.useState(false);
    const [scroll, setScroll] = React.useState<DialogProps['scroll']>('paper');

    const theme = useTheme();

    const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));

    useEffect(() => {
        const desc = description || 'No description available for this company.';
        let descStripped = desc;
        if (desc.length > contentStripLength && displayShowMore) {
            descStripped = toEndDottedStr(desc, contentStripLength);
        }
        setShowDesc(descStripped);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [description]);

    const source = showDesc.replace(/\\n/gi, '\n');

    const handleClickOpen = (scrollType: DialogProps['scroll']) => () => {
        setOpen(true);
        setScroll(scrollType);
    };

    const handleClose = () => {
        setOpen(false);
    };

    const descriptionElementRef = React.useRef<HTMLElement>(null);

    useEffect(() => {
        if (open) {
            const { current: descriptionElement } = descriptionElementRef;
            if (descriptionElement !== null) {
                descriptionElement.focus();
            }
        }
    }, [open]);

    return (
        <>
            {description && (
                <div>
                    <div onClick={onClick}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]} className={`m-0 p-0 mark-down-text ${markdownClassName}`}>
                            {source}
                        </ReactMarkdown>
                        {displayShowMore && description.length > contentStripLength && (
                            <Button fullWidth={false} variant="text" onClick={handleClickOpen('paper')} className={`show-more-less-text capitalize p-0 cursor-pointer !text-brand-500 hover:text-brand-600 ${textClassName}`}>
                                Read more
                            </Button>
                        )}
                    </div>
                    <Dialog
                        disableScrollLock
                        PaperProps={{
                            style: { borderRadius: '4px' }
                        }}
                        fullScreen={fullScreen}
                        open={open}
                        onClose={handleClose}
                        scroll={scroll}
                        aria-labelledby="scroll-dialog-title"
                        aria-describedby="scroll-dialog-description"
                    >
                        <DialogTitle className="flex justify-between items-center" id="scroll-dialog-title">
                            {scrollTitle}
                            <Button variant="outlined" onClick={handleClose}>
                                Close
                            </Button>
                        </DialogTitle>
                        <DialogContent dividers={scroll === 'paper'}>
                            <DialogContentText className="" id="scroll-dialog-description" ref={descriptionElementRef} tabIndex={-1}>
                                {description}
                            </DialogContentText>
                        </DialogContent>
                    </Dialog>
                </div>
            )}
            {!description && (
                <p className={`m-0 p-0 ${textClassName}`} style={{ color: '#9b9b9b' }}>
                    {source}
                </p>
            )}
        </>
    );
}
