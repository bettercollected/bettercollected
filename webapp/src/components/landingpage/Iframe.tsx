import { useRef } from 'react';

import CloseIcon from '@mui/icons-material/Close';
import Dialog from '@mui/material/Dialog';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';

import FormInput from '@app/components/ui/FormInput';
import FormRenderer from '@app/components/ui/FormRenderer';

/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-21
 * Time: 14:10
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function Iframe(props: any) {
    const { handleClose, formUrl } = props;

    const iframeRef = useRef(null);

    function handleIframe(e: any) {
        const currentIframe = e;
        console.log('submit', e);
        // if(!!currentIframe.current) {
        //     console.log("iframe", currentIframe.contentWindow.document.getElementsByTagName("a"))
        // }
    }

    return (
        <Dialog
            PaperProps={{
                sx: {
                    width: '640',
                    maxWidth: '720px!important',
                    overflow: 'hidden'
                }
            }}
            open={true}
            onClose={handleClose}
        >
            <DialogTitle>
                <div className={'flex justify-between items-center'}>
                    <h3>Please fill up the form below.</h3>
                    <CloseIcon className={'cursor-pointer'} onClick={handleClose} />
                </div>
            </DialogTitle>
            <DialogContent>
                <div className={'overflow-hidden'}>
                    <iframe
                        ref={iframeRef}
                        src={formUrl}
                        // src={`https://docs.google.com/forms/d/e/1FAIpQLSc-OA5vBjBLYm2xN2ZVxDuxqqrmwSHKAqAgv6QrF1TwIWKMow/viewform?emailAddress=${field}&embedded=true`}
                        // src={`https://docs.google.com/forms/d/e/1FAIpQLSfq2czYvDrNv0-aXvb7zrUTzMefScFRdO7nM52_A0vRdUkvOQ/viewform?emailAddress=${field}&embedded=true`}
                        width="640"
                        height="1900"
                        onLoad={handleIframe}
                        scrolling={'no'}
                        frameBorder={0}
                        marginHeight={0}
                        marginWidth={0}
                    >
                        Loading…
                    </iframe>
                </div>
            </DialogContent>
        </Dialog>
    );
}
