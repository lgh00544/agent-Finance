import { get, upload, UPLOAD_OCR_TIMEOUT } from './client'
import type { OcrResult, OcrStatus } from '@/types'

/** GET /api/ocr/status */
export const ocrStatus = (): Promise<OcrStatus> => get('/ocr/status')

/** POST /api/ocr/holding（multipart 上传持仓截图，timeout 180s） */
export const ocrHolding = (imageBytes: Blob, filename: string): Promise<OcrResult> =>
  upload('/ocr/holding', imageBytes, filename, undefined, undefined, UPLOAD_OCR_TIMEOUT)
