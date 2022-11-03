/**
 * Created By: Rupan Chaulagain
 * Date: 2022-11-02
 * Time: 21:57
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import { useRouter } from 'next/router';

export default function Oauthcallback() {
    const router = useRouter();
    console.log('router: ', router);
    return <div>Hello</div>;
}
