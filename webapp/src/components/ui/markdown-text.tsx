import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import { Dialog, DialogContent, DialogProps, DialogTitle, useMediaQuery, useTheme } from '@mui/material';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Absolute imports
import { Close } from '@app/components/icons/close';
import { localesDefault } from '@app/constants/locales';
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
    const { t } = useTranslation();
    const theme = useTheme();

    const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));

    useEffect(() => {
        const desc = description || t(localesDefault.noDescription);
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
                    <div onClick={onClick} className="body3 !text-black-700 !leading-tight">
                        <ReactMarkdown remarkPlugins={[remarkGfm]} className={`m-0 p-0 mark-down-text ${markdownClassName}`}>
                            {source}
                        </ReactMarkdown>
                        {displayShowMore && description.length > contentStripLength && (
                            <span onClick={handleClickOpen('paper')} className={`show-more-less-text hover:underline capitalize p-0 cursor-pointer !text-brand-500 hover:!text-brand-600 ${textClassName}`}>
                                {t(localesDefault.readMore)}
                            </span>
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
                        <DialogTitle className="relative flex justify-between items-center h4" id="scroll-dialog-title">
                            {scrollTitle}
                            <Close onClick={handleClose} className="cursor-pointer absolute top-3 right-3 h-auto w-3 text-gray-600 hover:text-black dark:text-white" />
                        </DialogTitle>
                        <DialogContent dividers={scroll === 'paper'}>
                            <ReactMarkdown remarkPlugins={[remarkGfm]} className={`m-0 p-0 mark-down-text ${markdownClassName}`}>
                                {description}
                            </ReactMarkdown>
                        </DialogContent>
                    </Dialog>
                </div>
            )}
            {!description && (
                <p className={`m-0 p-0 body3 !text-black-700 ${textClassName}`} style={{ color: '#9b9b9b' }}>
                    {source}
                </p>
            )}
        </>
    );
}
