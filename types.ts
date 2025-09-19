
export interface Person {
  id: string;
  firstName: string;
  middleName: string;
  lastName: string;
  born: string;
  died: string;
}

export interface OcrOptions {
  mode: 'standard' | 'handwritten' | 'damaged' | string;
  customPrompt?: string;
  language?: string;
  characterSet?: string;
  negativePrompt?: string;
}

export interface CemeteryRecord {
  imageFilename: string;
  plotLocation: string;
  gpsCoordinates: {
    latitude: string;
    longitude: string;
  };
  epitaph: string;
  people: Person[];
  ocrOptions: OcrOptions;
  streetViewPhotoFilename?: string;
}

export interface ImageFile {
  file: File;
  url: string;
}

export interface TransformState {
  zoom: number;
  pan: { x: number; y: number };
  rotation: number;
}

export interface SelectionRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Point {
  x: number;
  y: number;
}

export interface BatchProcessResult {
  status: 'success' | 'partial' | 'error';
  imageFilename: string;
  record?: CemeteryRecord;
  errorMessage?: string;
}

export type AiParsingProvider = 'google-ai' | 'lm-studio';
export type AiOcrProvider = 'google-ai' | 'local-ocr';

export interface LocalOcrSettings {
  url: string;
  apiKey?: string;
}

export interface AiSettings {
  parsing: AiParsingProvider;
  ocr: AiOcrProvider;
  localOcr: LocalOcrSettings;
}