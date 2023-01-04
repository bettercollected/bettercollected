import { useState } from 'react';

export default function LinearScale() {
    const scales = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    const [selectScale, setSelectScale] = useState(-1);

    return (
        <div className="mb-4">
            <h3 className="text-lg mb-2 font-medium">Linear Scale</h3>
            <div className="flex gap-6">
                {scales.map((s, idx) => (
                    <div key={s} className="flex flex-col">
                        <div
                            // onClick={() => setSelectScale(s)}
                            className={`w-[48px] ${selectScale === s ? 'border-blue-500 text-blue-500' : 'border-[#eaeaea]'} p-2 flex cursor-pointer justify-center items-center h-[48px] border-solid border-[2px] rounded-md text-xl font-extrabold`}
                        >
                            {s}
                        </div>
                        {s === 1 ? <div className="font-bold text-lg">Worst</div> : s === 10 ? <div className="font-bold text-lg text-end">Best</div> : <></>}
                    </div>
                ))}
            </div>
        </div>
    );
}
