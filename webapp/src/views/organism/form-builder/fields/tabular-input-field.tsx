'use client';

import { useEffect, useState, useCallback, useMemo } from 'react';
import { useFormState } from '@app/store/jotai/form';
import { Input } from '@app/shadcn/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@app/shadcn/components/ui/table';
import { useAtomValue } from 'jotai';
import { activeFieldAtom } from '@app/store/jotai/active-builder-component';
import { useBuilderActions } from '@app/store/jotai/field-selectors';
import { cn } from '@app/shadcn/util/lib';
import { Close } from '@app/components/icons/close';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useQuestionLabel } from '@app/views/molecules/responder-form-fields/question-label-context';

interface TabularInputFieldProps {
  value: string[][];
  onChange: (value: string[][]) => void;
  rowTitles: string[];
  columnTitles: string[];
  disabled?: boolean;
  fieldId?: string;
  field: StandardFormFieldDto;
  isActiveField?: boolean;
  onDeleteRow?: (rowIndex: number) => void;
  onDeleteColumn?: (colIndex: number) => void;
}

export default function TabularInputField({
  value,
  onChange,
  rowTitles,
  columnTitles,
  disabled = false,
  field,
  onDeleteRow,
  onDeleteColumn
}: TabularInputFieldProps) {
  const { theme } = useFormState();
  const { updateTabularRowTitle, updateTabularColumnTitle } = useBuilderActions();
  const activeField = useAtomValue(activeFieldAtom);
  // For respondents the table is named by its question and each cell by its
  // row and column titles (no question label on the builder canvas).
  const { group } = useQuestionLabel();
  const rowHeaderId = (rowIdx: number) => `table-${field.id}-row-${rowIdx}`;
  const columnHeaderId = (colIdx: number) => `table-${field.id}-col-${colIdx}`;

  const minRows = 2;
  const minCols = 2;

  const columns = useMemo(() => 
    columnTitles?.length >= minCols ? columnTitles : Array(minCols).fill('').map((_, i) => `Col ${i + 1}`),
    [columnTitles]
  );

  const rows = useMemo(() => 
    rowTitles?.length >= minRows ? rowTitles : Array(minRows).fill('').map((_, i) => `Row ${i + 1}`), 
    [rowTitles]
  );

  const initialTableValue = useMemo(() => {
    if (value && value.length >= rows.length && value[0]?.length >= columns.length) return value;
    return rows.map(() => columns.map(() => ''));
  }, [value, rows.length, columns.length]);

  const [tableData, setTableData] = useState<string[][]>(initialTableValue);
  const [localRowTitles, setLocalRowTitles] = useState(rows);
  const [localColTitles, setLocalColTitles] = useState(columns);

  // Sync internal state with props
  useEffect(() => { setTableData(initialTableValue); }, [initialTableValue]);
  useEffect(() => { setLocalRowTitles(rows); }, [rows]);
  useEffect(() => { setLocalColTitles(columns); }, [columns]);

  const handleInputChange = useCallback((rowIdx: number, colIdx: number, val: string) => {
    const updated = tableData.map((row, r) =>
      row.map((cell, c) => (r === rowIdx && c === colIdx ? val : cell))
    );
    setTableData(updated);
    onChange(updated);
  }, [tableData, onChange]);

  const handleRowTitleChange = useCallback((rowIdx: number, val: string) => {
    const updated = [...localRowTitles];
    updated[rowIdx] = val;
    setLocalRowTitles(updated);
    updateTabularRowTitle(rowIdx, val);
  }, [localRowTitles, updateTabularRowTitle]);

  const handleColTitleChange = useCallback((colIdx: number, val: string) => {
    const updated = [...localColTitles];
    updated[colIdx] = val;
    setLocalColTitles(updated);
    updateTabularColumnTitle(colIdx, val);
  }, [localColTitles, updateTabularColumnTitle]);

  const sharedHeaderStyle = {
    background: (theme?.tertiary ?? '') + '55',
    borderColor: theme?.secondary,
    color: theme?.secondary,
  };

  return (
    <div className="w-full overflow-hidden rounded border border-black-300">
      <div 
        className={cn(
          "overflow-x-auto rounded-lg border custom-scrollbar", 
          "scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent"
        )} 
        style={{ borderColor: theme?.secondary }}
      >
        <Table className="min-w-max w-full border-collapse" {...group}>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {/* The empty corner is a plain cell: an empty header names nothing. */}
              <TableCell
                className="sticky left-0 z-20 h-12 min-w-24 max-w-40 border-r border-b border-t-[2px] border-black-300 px-4 py-0"
                style={sharedHeaderStyle}
              />
              {localColTitles.map((col, idx) => (
                <TableHead
                  key={idx}
                  id={columnHeaderId(idx)}
                  className={cn(
                    "relative group text-center font-semibold px-3 py-3 min-w-28 max-w-48 border-r border-b border-t-[2px]",
                    idx === localColTitles.length - 1 && "rounded-tr-lg border-r-[2px]"
                  )}
                  style={sharedHeaderStyle}
                >
                  {disabled && activeField?.id === field.id && localColTitles.length > minCols && (
                    <button
                      type="button"
                      aria-label={`Remove column ${idx + 1}`}
                      className="absolute left-1 top-1 rounded-full bg-white p-1 opacity-50 h-5 w-5 cursor-pointer hover:opacity-100 focus-visible:opacity-100 z-10 flex items-center justify-center transition-opacity"
                      onClick={() => onDeleteColumn?.(idx)}
                    >
                      <Close className="h-3 w-3" aria-hidden="true" />
                    </button>
                  )}
                  {disabled ? (
                    <Input
                      value={col ?? ''}
                      onChange={(e) => handleColTitleChange(idx, e.target.value)}
                      className="text-center font-semibold text-sm! bg-transparent border-none focus:ring-0 h-8"
                    />
                  ) : (
                    <span className="text-sm">{col}</span>
                  )}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>

          <TableBody>
            {tableData.map((row, rowIdx) => (
              <TableRow key={rowIdx} className="hover:bg-muted/10 transition-colors">
                <TableCell
                  id={rowHeaderId(rowIdx)}
                  className={cn(
                    "sticky left-0 z-10 min-w-24 max-w-40 px-3 py-2 font-medium text-center border-r border-b border-black-300",
                    rowIdx === tableData.length - 1 && "rounded-bl-lg border-b-[2px]"
                  )}
                  style={sharedHeaderStyle}
                >
                  {disabled && activeField?.id === field.id && tableData.length > minRows && (
                    <button
                      type="button"
                      aria-label={`Remove row ${rowIdx + 1}`}
                      className="absolute left-1 top-1 rounded-full bg-white p-1 opacity-50 h-5 w-5 cursor-pointer hover:opacity-100 focus-visible:opacity-100 z-10 flex items-center justify-center transition-opacity"
                      onClick={() => onDeleteRow?.(rowIdx)}
                    >
                      <Close className="h-3 w-3" aria-hidden="true" />
                    </button>
                  )}
                  {disabled ? (
                    <Input
                      value={localRowTitles[rowIdx] ?? ''}
                      onChange={(e) => handleRowTitleChange(rowIdx, e.target.value)}
                      className="text-center font-semibold text-sm! bg-transparent border-none focus:ring-0 h-8"
                    />
                  ) : (
                    <span className="text-sm">{localRowTitles[rowIdx]}</span>
                  )}
                </TableCell>

                {row.map((cell, colIdx) => (
                  <TableCell
                    key={colIdx}
                    className={cn(
                      "px-3 py-2 text-center border-r border-b",
                      rowIdx === tableData.length - 1 && colIdx === row.length - 1 && "rounded-br-lg border-b-[2px]",
                      colIdx === row.length - 1 && "border-r-[2px]"
                    )}
                    style={{
                      background: theme?.accent,
                      borderColor: theme?.secondary,
                      color: theme?.secondary
                    }}
                  >
                    <Input
                      value={cell ?? ''}
                      disabled={disabled}
                      aria-labelledby={`${rowHeaderId(rowIdx)} ${columnHeaderId(colIdx)}`}
                      onChange={(e) => handleInputChange(rowIdx, colIdx, e.target.value)}
                      className="text-center text-sm! bg-transparent border-none focus:ring-0 h-8"
                    />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}