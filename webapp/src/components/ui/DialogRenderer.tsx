/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-18
 * Time: 10:43
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import CloseOutlinedIcon from '@mui/icons-material/CloseOutlined';

export default function DialogRenderer(props:any) {
    const {title, description, handleClose} = props;
    return(
        <Dialog
            open={true}
            onClose={handleClose}
            aria-labelledby="alert-dialog-title"
            aria-describedby="alert-dialog-description"
        >
            <DialogTitle id="alert-dialog-title" className={"flex justify-between items-center"}>
                {title}
                <CloseOutlinedIcon onClick={handleClose} className={"cursor-pointer text-gray-500"}/>
            </DialogTitle>
            <DialogContent>
                <DialogContentText id="alert-dialog-description">
                    {description}
                </DialogContentText>
            </DialogContent>
        </Dialog>
    )
}