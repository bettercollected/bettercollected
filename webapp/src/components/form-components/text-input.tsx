import { Copy } from '../icons/copy';

export default function TextInput({ children, title }: any) {
    return (
        <div className="mb-4">
            <h3 className="text-lg mb-2 font-medium">{title}</h3>
            <label htmlFor="first_name" className="relative block mb-2 text-sm font-medium text-gray-900 dark:text-white">
                {!!children && children}
                <input type="text" disabled id="first_name" className={`border-[1px] rounded-r-0 border-solid w-full border-[#eaeaea] text-sm rounded-md block lg:w-1/2 p-2.5 required`} />
            </label>
        </div>
    );
}
