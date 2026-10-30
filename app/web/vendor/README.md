Vendored so the tablet never loads code from the internet.
- barcode.js: barcode-detector 3.2.2 (MIT, github.com/Sec-ant/barcode-detector) bundled with esbuild,
  exporting BarcodeDetector and prepareZXingModule from "barcode-detector/ponyfill".
- zxing_reader.wasm: zxing-wasm 3.1.3 (MIT), which wraps zxing-cpp (Apache-2.0).
