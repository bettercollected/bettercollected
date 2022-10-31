import GoogleIcon from '@mui/icons-material/Google';

/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-13
 * Time: 06:19
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function IconsRender({ IconsArray }: any) {
    return (
        <div className={'flex gap-1'}>
            {IconsArray.map((icon: any, index: number) => (
                <div key={index} className={'p-2 border-gray-100 rounded-lg rounded-tr-none rounded-bl-none border-solid  border-[2px]'}>
                    {icon.Icon}
                </div>
            ))}
        </div>
    );
}
