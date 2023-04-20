import { Input, InputProps } from '@mui/material';

export default function BetterInput(props: InputProps) {
    const { className, ...otherProps } = props;
    return <Input {...otherProps} className={` border !border-solid flex-1 w-full placeholder:font-normal placeholder:text-sm placeholder:tracking-normal mb-4 !rounded-[1px] !h-[50px] text-gray-900 p-2.5` + className} />;
}
