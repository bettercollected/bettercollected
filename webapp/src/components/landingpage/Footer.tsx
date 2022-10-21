/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-20
 * Time: 16:26
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import {useRouter} from "next/router";
import TwitterIcon from '@mui/icons-material/Twitter';
import FacebookIcon from '@mui/icons-material/Facebook';
import InstagramIcon from '@mui/icons-material/Instagram';

export default function Footer() {
    let currentYear = new Date().getFullYear();
    const router = useRouter();

    function SectionLink(props:any) {
        const {title, path} = props;
        return <p className={"cursor-pointer mb-2 hover:text-gray-600"} onClick={() => router.push(`#${path}`)}>{title}</p>
    }

    function FontBold(props:any){
        return (
          <div className={"font-semibold mb-2"}>
              {props.children}
          </div>
        );
    }


    return (
        <div className={"flex flex-col md:flex w-full md:flex-row bg-[#f5faff] border-[#b8daff] border-t-[1px] justify-around items-start p-4 "}>

            <div className={"flex flex-col"}>
                <div className={"font-bold text-2xl font-roboto tracking-widest mb-4"}>
                    Better<span className={"text-[#007AFF] tracking-widest"}>Collected.</span>
                </div>
                {/*<FontBold>Sanepa-2</FontBold>*/}
                {/*<FontBold>Lalitpur Nepal</FontBold>*/}
            </div>

            <div className={"flex flex-col justify-center lg:items-center lg:mb-0 mb-4"}>
                <FontBold>Company</FontBold>
                <SectionLink title={"Home"} path={""}/>
                <SectionLink title={"Features"} path={"features"}/>
                <SectionLink title={"Contact"} path={"contact"}/>
            </div>

            <div className={"flex flex-col mb-4"}>
                <FontBold>Follow Us</FontBold>
                <div className={"flex gap-2"}>
                    <TwitterIcon className={"bg-gray-300 hover:bg-gray-200 cursor-pointer rounded-md p-1 h-7 w-7"}/>
                    <FacebookIcon className={"bg-gray-300 hover:bg-gray-200 cursor-pointer rounded-md p-1 h-7 w-7"}/>
                    <InstagramIcon className={"bg-gray-300 hover:bg-gray-200 cursor-pointer rounded-md p-1 h-7 w-7"}/>
                </div>
            </div>

            <div className={"flex flex-col"}>
                <h3 className={"font-semibold text-md mb-4 cursor-pointer hover:text-gray-500"}>Terms and Conditions</h3>
                <h3 className={"font-semibold text-md mb-4 lg:mb-0 cursor-pointer hover:text-gray-500"}>Privacy Policy</h3>
            </div>
        </div>
    )
}