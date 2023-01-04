export default function MultipleChoiceGrid() {
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
                    <label key={idx} className="flex flex-col justify-center items-center">
                        {<p>{column}</p>}
                        <input disabled id="default-radio-1" type="radio" value="" name="default-radio" className="w-4 h-4 ring-0 active:bg-red focus:ring-offset-0 focus:ring-0 text-blue-600 border-[#c7c7c7]" />
                    </label>
                </div>
            ))}
        </>
    );

    return (
        <div className="mb-4">
            <h3 className="text-lg mb-2 font-medium">Multiple Choice Grid</h3>
            <div className={'border-solid w-fit rounded-md border-[1px] border-[#eaeaea] p-6'}>
                {grids.map((grid, idx) => (
                    <div key={idx} className="flex w-full mb-2 gap-10">
                        <p className="font-semibold text-lg">{grid.title}</p>
                        <div className="flex gap-10 items-center">
                            <RowRenderer columnArray={grid.column} />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
