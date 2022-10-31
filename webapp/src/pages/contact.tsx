/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-22
 * Time: 09:38
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import environments from '@app/configs/environments';

export default function WaitlistForms() {
    return (
        <div className={'absolute left-0 right-0 top-0 bottom-0'}>
            <iframe src={environments.CONTACT_US_URL} height={'100%'} width={'100%'}>
                Loading…
            </iframe>
        </div>
    );
}
