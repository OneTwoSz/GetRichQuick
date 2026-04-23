/**
 * BillUpload
 * ----------
 * Drop-in "Upload bill / invoice" assist for data-entry forms.
 *
 * Flow:
 *   1. User picks a file (phone photo of an electricity bill, for example).
 *   2. Component POSTs it to /api/ocr/extract with the given hint.
 *   3. Component shows the extracted fields in a confirmation panel with a
 *      confidence indicator and any caveats from the model.
 *   4. On "Apply", the parent receives the fields via `onApply` and decides
 *      how to map them into its own form state.
 *
 * Design notes
 *   - OCR is ASSIST. We never submit directly. The parent is responsible for
 *     writing anything to the backend.
 *   - Model output is displayed as-is (including the 'notes' caveat) so the
 *     user understands when to double-check.
 *   - Errors surface inline, not via alert().
 */
import { useRef, useState } from 'react';
import { ocrAPI, type OcrHint, type OcrResponse } from '@/services/api';

interface BillUploadProps {
  hint: OcrHint;
  label?: string;
  helpText?: string;
  onApply: (fields: Record<string, unknown>, raw: OcrResponse) => void;
}

const HINT_LABELS: Record<OcrHint, string> = {
  electricity_bill: 'Electricity bill',
  water_bill: 'Water bill',
  dye_invoice: 'Dye / chemical invoice',
  fabric_invoice: 'Fabric / yarn invoice',
};

export default function BillUpload({ hint, label, helpText, onApply }: BillUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<OcrResponse | null>(null);

  const resolvedLabel = label ?? `Upload ${HINT_LABELS[hint]}`;

  const reset = () => {
    setFile(null);
    setResult(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  const handleSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const next = e.target.files?.[0] ?? null;
    setFile(next);
    setResult(null);
    setError(null);
  };

  const handleExtract = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const res = await ocrAPI.extract(file, hint);
      setResult(res);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'OCR failed';
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally {
      setBusy(false);
    }
  };

  const handleApply = () => {
    if (!result) return;
    onApply(result.fields, result);
    reset();
  };

  const confidencePct = result ? Math.round((result.confidence || 0) * 100) : 0;
  const confidenceColor =
    confidencePct >= 80 ? 'text-green-700' : confidencePct >= 50 ? 'text-amber-700' : 'text-red-700';

  return (
    <div className="border border-dashed border-gray-300 rounded-lg p-4 bg-gray-50">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-gray-900">{resolvedLabel}</div>
          {helpText && <p className="text-xs text-gray-600 mt-1">{helpText}</p>}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,application/pdf"
          onChange={handleSelect}
          className="text-xs"
        />
      </div>

      {file && !result && (
        <div className="mt-3 flex items-center gap-2">
          <span className="text-xs text-gray-600 truncate">{file.name}</span>
          <button
            type="button"
            onClick={handleExtract}
            disabled={busy}
            className="ml-auto px-3 py-1 text-xs bg-primary text-white rounded hover:bg-primary-600 disabled:opacity-50"
          >
            {busy ? 'Reading…' : 'Extract fields'}
          </button>
          <button
            type="button"
            onClick={reset}
            disabled={busy}
            className="px-2 py-1 text-xs text-gray-600 hover:text-gray-900"
          >
            Clear
          </button>
        </div>
      )}

      {error && (
        <div className="mt-3 text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-3 bg-white border border-gray-200 rounded p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-600">
              Model confidence:{' '}
              <span className={`font-semibold ${confidenceColor}`}>{confidencePct}%</span>
            </span>
            <span className="text-xs text-gray-500">{result.filename}</span>
          </div>

          {result.notes && (
            <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded p-2">
              <span className="font-medium">Check this: </span>
              {result.notes}
            </div>
          )}

          <div className="text-xs">
            <div className="font-medium text-gray-900 mb-1">Extracted:</div>
            <pre className="bg-gray-50 p-2 rounded overflow-x-auto text-gray-800 text-[11px]">
              {JSON.stringify(result.fields, null, 2)}
            </pre>
          </div>

          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={handleApply}
              className="px-3 py-1 text-xs bg-primary text-white rounded hover:bg-primary-600"
            >
              Apply to form
            </button>
            <button
              type="button"
              onClick={reset}
              className="px-3 py-1 text-xs border border-gray-300 text-gray-700 rounded hover:bg-gray-50"
            >
              Discard
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
