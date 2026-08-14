// تایپِ محیطیِ Barcode Detection API — هنوز در tslib استاندارد نیست.
// در Chrome اندروید و Chromium/الکترون موجود است؛ روی Safari/فایرفاکس نیست،
// پس همیشه از راهِ `window.BarcodeDetector` (اختیاری) استفاده می‌شود، نه گلوبالِ برهنه.

interface DetectedBarcode {
  rawValue: string
  format: string
  boundingBox: DOMRectReadOnly
  cornerPoints: { x: number; y: number }[]
}

declare class BarcodeDetector {
  constructor(options?: { formats?: string[] })
  static getSupportedFormats(): Promise<string[]>
  detect(source: CanvasImageSource): Promise<DetectedBarcode[]>
}

interface Window {
  BarcodeDetector?: typeof BarcodeDetector
}
