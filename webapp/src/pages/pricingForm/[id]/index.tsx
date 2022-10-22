import environments from "@app/configs/environments";
import {useRouter} from "next/router";

/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-22
 * Time: 10:40
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
export default function Index(){
    const router = useRouter();
    const plan = router.query.id;
    console.log(router)
    return (
        <div className={"absolute left-0 right-0 top-0 bottom-0"}>
            <iframe
                src={`${environments.PRICING_URL}&entry.1920448317=${plan}`}
                height={"100%"} width={"100%"}>Loading…
            </iframe>
        </div>
    );
}