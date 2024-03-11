import { useQRCode } from 'next-qrcode';

import { useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { StandardFormDto } from '@app/models/dtos/form';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import getFormShareURL from '@app/utils/formUtils';

const QRGenerator = ({ form }: { form: StandardFormDto }) => {
    const { Canvas } = useQRCode();
    const workspace = useAppSelector(selectWorkspace);
    const formUrl = getFormShareURL(form, workspace);
    const isMobile = useIsMobile();

    return (
        <div id={'form-qr-code'}>
            <Canvas
                text={formUrl}
                options={{
                    errorCorrectionLevel: 'M',
                    margin: 3,
                    scale: 8,
                    width: isMobile ? 220 : 260,
                    color: {
                        light: '#DBDBDB',
                        dark: '#0764EB'
                    }
                }}
            />
        </div>
    );
};

export default QRGenerator;
