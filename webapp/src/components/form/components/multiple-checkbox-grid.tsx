import { grid } from '@mui/system';

export default function MultipleCheckboxGrid() {
    const grids = [
        {
            title: 'Row 1',
            column: ['Column 1', 'Column 2', 'Column 3', 'Column 4']
        },
        {
            title: 'Row 2',
            column: ['Column 1', 'Column 2', 'Column 3', 'Column 4']
        },
        {
            title: 'Row 3',
            column: ['Column 1', 'Column 2', 'Column 3', 'Column 4']
        }
    ];
    const RowRenderer = ({ columnArray }: any) => (
        <>
            {columnArray.map((column: any, idx: any) => (
                <div key={idx} className="gap-y-6">
                    <label className="flex flex-col justify-center items-center">
                        {<p>{column}</p>}
                        <input
                            id="default-checkbox"
                            type="checkbox"
                            value=""
                            disabled
                            className="w-6 h-6 text-blue-600 rounded border-[#eaeaea] focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-gray-700 dark:border-gray-600"
                        />
                    </label>
                </div>
            ))}
        </>
    );

    return (
        <div className="mb-4">
            <h3 className="text-lg mb-2 font-medium">Multiple Checkbox Grid</h3>
            <div className={'border-solid w-fit rounded-md border-[1px] border-[#eaeaea] p-6'}>
                {grids.map((grid, idx) => (
                    <div key={idx} className="flex w-full mb-2 gap-10">
                        <p className="font-semibold text-lg">{grid.title}</p>
                        <div className="flex gap-10 items-center">
                            {/* {grid.title} */}
                            <RowRenderer columnArray={grid.column} />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
