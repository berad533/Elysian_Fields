
import React, { useState, useRef, useCallback, useEffect, ChangeEvent, memo, useMemo } from 'react';
import type { ImageFile, CemeteryRecord, Person, TransformState, SelectionRect, Point, OcrOptions, BatchProcessResult, AiSettings, AiParsingProvider, AiOcrProvider, LocalOcrSettings } from './types';
import { extractTextFromImage, parseOcrTextToRecord, extractAndParseImage, parseWithLmStudio, testLocalConnection } from './services/geminiService';
import { LocalServiceConnector } from './services/localServiceConnector';
import type L from 'leaflet';

// Fix: Add webkitdirectory to React's input element properties to resolve TypeScript error for selecting directories.
declare module 'react' {
    interface InputHTMLAttributes<T> {
        webkitdirectory?: string;
    }
}

// --- Helper Functions, Constants & Hooks ---

const INITIAL_TRANSFORM: TransformState = { zoom: 1, pan: { x: 0, y: 0 }, rotation: 0 };
const DEFAULT_OCR_OPTIONS: OcrOptions = {
    mode: 'standard',
    customPrompt: '',
    language: '',
    characterSet: '',
    negativePrompt: '',
};

/**
 * Converts DMS (Degrees, Minutes, Seconds) from EXIF to decimal degrees.
 */
const convertDMSToDD = (dms: number[], ref: string): number => {
    const degrees = dms[0] || 0;
    const minutes = dms[1] || 0;
    const seconds = dms[2] || 0;
    let dd = degrees + minutes / 60 + seconds / 3600;
    if (ref === 'S' || ref === 'W') {
        dd = dd * -1;
    }
    return dd;
};

/**
 * Parses a File object to extract GPS coordinates from its EXIF metadata.
 * @param file The image file to parse.
 * @returns A promise that resolves to an object with latitude and longitude, or null if not found.
 */
async function getGpsFromExif(file: File): Promise<{ latitude: number; longitude: number } | null> {
    return new Promise((resolve) => {
        const reader = new FileReader();

        reader.onload = (event) => {
            try {
                if (!event.target?.result) return resolve(null);
                
                const view = new DataView(event.target.result as ArrayBuffer);

                // FIX: Moved helper functions inside the try block to give them access to the `view` variable.
                function findTag(ifdStart: number, tag: number, isBigEndian: boolean) {
                    const count = view.getUint16(ifdStart, isBigEndian);
                    for (let i = 0; i < count; i++) {
                        const entryOffset = ifdStart + 2 + (i * 12);
                        if (view.getUint16(entryOffset, isBigEndian) === tag) {
                            return entryOffset;
                        }
                    }
                    return null;
                }

                function readTagValue(tiffStart: number, entryOffset: number, isBigEndian: boolean): string | number[] | null {
                    const type = view.getUint16(entryOffset + 2, isBigEndian);
                    const count = view.getUint32(entryOffset + 4, isBigEndian);
                    const valueOffset = view.getUint32(entryOffset + 8, isBigEndian);

                    switch (type) {
                        case 2: // ASCII
                            return String.fromCharCode(view.getUint8(tiffStart + valueOffset));
                        case 5: { // Unsigned Rational
                            const values: number[] = [];
                            for (let i = 0; i < count; i++) {
                                const num = view.getUint32(tiffStart + valueOffset + i * 8, isBigEndian);
                                const den = view.getUint32(tiffStart + valueOffset + i * 8 + 4, isBigEndian);
                                values.push(den === 0 ? 0 : num / den);
                            }
                            return values;
                        }
                    }
                    return null;
                }
                
                function findGpsIFD(tiffStart: number, ifdStart: number, isBigEndian: boolean): number | null {
                    const numEntries = view.getUint16(ifdStart, isBigEndian);
                    for (let i = 0; i < numEntries; i++) {
                        const entryOffset = ifdStart + 2 + (i * 12);
                        if (view.getUint16(entryOffset, isBigEndian) === 0x8825) { // GPS Info IFD Pointer
                            return view.getUint32(entryOffset + 8, isBigEndian);
                        }
                    }
                    const nextIFDOffset = view.getUint32(ifdStart + 2 + numEntries * 12, isBigEndian);
                    if (nextIFDOffset !== 0) {
                       return findGpsIFD(tiffStart, tiffStart + nextIFDOffset, isBigEndian);
                    }
                    return null;
                }

                // FIX: Updated function to return null on failure for clearer type checking.
                function parseGpsIFD(tiffStart: number, gpsIfdStart: number, isBigEndian: boolean): { latitude: number, longitude: number } | null {
                    const latRefEntry = findTag(gpsIfdStart, 0x0001, isBigEndian);
                    const latEntry = findTag(gpsIfdStart, 0x0002, isBigEndian);
                    const lonRefEntry = findTag(gpsIfdStart, 0x0003, isBigEndian);
                    const lonEntry = findTag(gpsIfdStart, 0x0004, isBigEndian);

                    if (latRefEntry && latEntry && lonRefEntry && lonEntry) {
                        const latRef = readTagValue(tiffStart, latRefEntry, isBigEndian);
                        const latDMS = readTagValue(tiffStart, latEntry, isBigEndian);
                        const lonRef = readTagValue(tiffStart, lonRefEntry, isBigEndian);
                        const lonDMS = readTagValue(tiffStart, lonEntry, isBigEndian);
                        
                        if (latRef && Array.isArray(latDMS) && lonRef && Array.isArray(lonDMS)) {
                            return {
                                latitude: convertDMSToDD(latDMS, latRef as string),
                                longitude: convertDMSToDD(lonDMS, lonRef as string)
                            };
                        }
                    }
                    return null;
                }

                if (view.getUint16(0, false) !== 0xFFD8) {
                    return resolve(null); // Not a JPEG
                }

                let offset = 2;
                const length = view.byteLength;

                while (offset < length) {
                    if (view.getUint8(offset) !== 0xFF) {
                        return resolve(null); // Corrupted file
                    }

                    const marker = view.getUint8(offset + 1);

                    if (marker === 0xE1) { // APP1 marker for EXIF
                        const tiffOffset = offset + 10;
                        if (view.getUint32(offset + 4, false) !== 0x45786966) { // "Exif"
                           return resolve(null);
                        }

                        const bigEndian = view.getUint16(tiffOffset, false) === 0x4D4D;
                        
                        if (view.getUint16(tiffOffset + 2, bigEndian) !== 0x002A) {
                            return resolve(null); // Invalid TIFF alignment
                        }
                        
                        const firstIFDOffset = view.getUint32(tiffOffset + 4, bigEndian);
                        if (firstIFDOffset < 8) {
                            return resolve(null); // Invalid offset
                        }

                        const gpsIFDOffset = findGpsIFD(tiffOffset, tiffOffset + firstIFDOffset, bigEndian);

                        if (gpsIFDOffset) {
                            const gpsData = parseGpsIFD(tiffOffset, tiffOffset + gpsIFDOffset, bigEndian);
                            // FIX: Simplified check now that parseGpsIFD returns null on failure. This resolves the type error.
                            if (gpsData) {
                                return resolve(gpsData);
                            }
                        }
                        // Continue searching if this APP1 didn't have GPS
                    }
                    offset += 2 + view.getUint16(offset + 2, false);
                }
                return resolve(null);
            } catch (e) {
                console.error("Error parsing EXIF data:", e);
                return resolve(null);
            }
        };

        reader.onerror = () => resolve(null);

        // Read the first 128KB of the file, which is more than enough for EXIF data.
        reader.readAsArrayBuffer(file.slice(0, 128 * 1024));
    });
}


/**
 * Capitalizes each word in a string, handling spaces and hyphens.
 * e.g., "mary-anne smith" -> "Mary-Anne Smith"
 */
const capitalizeName = (name: string): string => {
    if (!name || typeof name !== 'string') return '';
    const capitalizePart = (part: string) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase();
    
    return name
        .split(' ')
        .map(word => 
            word.split('-').map(capitalizePart).join('-')
        )
        .join(' ');
};

/**
 * A simple, fast object equality check.
 */
const isEqual = (a: any, b: any): boolean => JSON.stringify(a) === JSON.stringify(b);

/**
 * Custom hook to manage state with undo/redo capabilities.
 */
function useHistoryState<T>(initialState: T) {
    const [state, setState] = useState({
        past: [] as T[],
        present: initialState,
        future: [] as T[],
    });

    const canUndo = state.past.length > 0;
    const canRedo = state.future.length > 0;

    const set = useCallback((action: T | ((prevState: T) => T)) => {
        setState(currentState => {
            const newPresent = typeof action === 'function'
                ? (action as (prevState: T) => T)(currentState.present)
                : action;
            
            if (isEqual(newPresent, currentState.present)) {
                return currentState;
            }

            return {
                past: [...currentState.past, currentState.present],
                present: newPresent,
                future: [],
            };
        });
    }, []);

    const undo = useCallback(() => {
        setState(currentState => {
            if (currentState.past.length === 0) return currentState;
            const previous = currentState.past[currentState.past.length - 1];
            const newPast = currentState.past.slice(0, currentState.past.length - 1);
            return {
                past: newPast,
                present: previous,
                future: [currentState.present, ...currentState.future],
            };
        });
    }, []);

    const redo = useCallback(() => {
        setState(currentState => {
            if (currentState.future.length === 0) return currentState;
            const next = currentState.future[0];
            const newFuture = currentState.future.slice(1);
            return {
                past: [...currentState.past, currentState.present],
                present: next,
                future: newFuture,
            };
        });
    }, []);

    const reset = useCallback((newState: T) => {
        setState({
            past: [],
            present: newState,
            future: [],
        });
    }, []);

    return { state: state.present, set, undo, redo, canUndo, canRedo, reset };
}

/**
 * Custom hook for creating a debounced version of a callback function.
 * @returns A tuple containing the debounced function and a function to cancel any pending execution.
 */
function useDebouncedCallback<A extends any[]>(
  callback: (...args: A) => void,
  delay: number
): [(...args: A) => void, () => void] {
  const timeoutRef = useRef<number | null>(null);

  const cancel = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    return cancel; // Cleanup on unmount
  }, [cancel]);

  const debouncedCallback = useCallback((...args: A) => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = window.setTimeout(() => {
      callback(...args);
    }, delay);
  }, [callback, delay]);

  return [debouncedCallback, cancel];
}


/**
 * Converts a point from screen/container space to the image's local coordinate space.
 */
const screenToImagePoint = (point: Point, transform: TransformState, container: { width: number, height: number }, image: {width: number, height: number}): Point => {
    const { zoom, pan, rotation } = transform;
    const rad = rotation * (Math.PI / 180);
    const cos = Math.cos(rad);
    const sin = Math.sin(rad);

    const containerCenterX = container.width / 2;
    const containerCenterY = container.height / 2;
    
    let x = point.x - (containerCenterX + pan.x);
    let y = point.y - (containerCenterY + pan.y);

    x /= zoom;
    y /= zoom;

    const rotX = x * cos + y * sin;
    const rotY = -x * sin + y * cos;
    
    return {
        x: rotX + (image.width / 2),
        y: rotY + (image.height / 2)
    };
};


const fileListToImageFile = (files: FileList | null): ImageFile[] => {
  if (!files) return [];
  return Array.from(files)
    .filter(file => file.type.startsWith('image/'))
    .map(file => ({ file, url: URL.createObjectURL(file) }));
};

const getCroppedBase64 = (imageElement: HTMLImageElement, selection: SelectionRect): Promise<{base64: string, mimeType: string}> => {
    return new Promise((resolve, reject) => {
        const canvas = document.createElement('canvas');
        canvas.width = selection.width;
        canvas.height = selection.height;
        const ctx = canvas.getContext('2d');

        if (!ctx) return reject(new Error('Could not get canvas context'));
        
        ctx.drawImage(
            imageElement,
            selection.x, selection.y, selection.width, selection.height,
            0, 0, selection.width, selection.height
        );
        
        const mimeType = 'image/jpeg';
        const base64 = canvas.toDataURL(mimeType).split(',')[1];
        resolve({ base64, mimeType });
    });
};

const getFullImageBase64 = (image: HTMLImageElement, mimeType: string): Promise<string> => {
    return new Promise((resolve, reject) => {
        const canvas = document.createElement('canvas');
        canvas.width = image.naturalWidth;
        canvas.height = image.naturalHeight;
        const ctx = canvas.getContext('2d');
        if (!ctx) return reject(new Error('Could not get canvas context'));
        ctx.drawImage(image, 0, 0);
        const base64 = canvas.toDataURL(mimeType).split(',')[1];
        resolve(base64);
    });
};


// --- UI Components ---

const Panel: React.FC<{ children: React.ReactNode; className?: string; }> = ({ children, className = '' }) => (
    <div className={`bg-gray-700 rounded-lg shadow-lg p-4 ${className}`}>
        {children}
    </div>
);

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'secondary' | 'danger' | 'warning';
}
const Button = memo(React.forwardRef<HTMLButtonElement, ButtonProps>(({ children, className, variant = 'primary', ...props }, ref) => {
    const baseClasses = "px-4 py-2 rounded-md font-semibold focus:outline-none focus:ring-2 focus:ring-opacity-75 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed";
    const variantClasses = {
        primary: "bg-indigo-600 hover:bg-indigo-700 focus:ring-indigo-500 text-white",
        secondary: "bg-gray-600 hover:bg-gray-500 focus:ring-gray-400 text-gray-100",
        danger: "bg-red-600 hover:bg-red-700 focus:ring-red-500 text-white",
        warning: "bg-amber-600 hover:bg-amber-700 focus:ring-amber-500 text-white",
    };
    return (
        <button ref={ref} className={`${baseClasses} ${variantClasses[variant]} ${className}`} {...props}>
            {children}
        </button>
    );
}));

// --- Memoized Child Components for Performance ---

const ImageWorkstation = memo(function ImageWorkstation({
    currentImage, liveTransform, ocrSelection, selection, drawingSelection,
    onWheel, onMouseDown, onMouseMove, onMouseUp, onMouseLeave, onContextMenu, onImageRef
}: {
    currentImage: ImageFile | undefined,
    liveTransform: TransformState,
    ocrSelection: SelectionRect | null,
    selection: SelectionRect | null,
    drawingSelection: SelectionRect | null,
    onWheel: (e: React.WheelEvent<HTMLDivElement>) => void,
    onMouseDown: (e: React.MouseEvent<HTMLDivElement>) => void,
    onMouseMove: (e: React.MouseEvent<HTMLDivElement>) => void,
    onMouseUp: () => void,
    onMouseLeave: () => void,
    onContextMenu: (e: React.MouseEvent<HTMLDivElement>) => void,
    onImageRef: React.Ref<HTMLImageElement>
}) {
    const imageContainerRef = useRef<HTMLDivElement>(null);
    // FIX: Get the image element from the ref to safely access its properties for rendering selections.
    const image = (onImageRef as React.RefObject<HTMLImageElement>)?.current;
    return (
        <div
            ref={imageContainerRef}
            className="w-full h-full bg-black rounded-lg overflow-hidden cursor-crosshair relative touch-none"
            onWheel={onWheel}
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={onMouseLeave}
            onContextMenu={onContextMenu}
        >
            {currentImage && (
                <>
                    <div
                        className="absolute top-1/2 left-1/2"
                        style={{
                            transform: `translate(${liveTransform.pan.x}px, ${liveTransform.pan.y}px) scale(${liveTransform.zoom}) rotate(${liveTransform.rotation}deg)`,
                            transformOrigin: '0 0',
                            willChange: 'transform'
                        }}
                    >
                        <img
                            ref={onImageRef}
                            src={currentImage.url}
                            alt="Headstone"
                            className="max-w-none"
                            style={{ transform: 'translate(-50%, -50%)'}}
                            draggable="false"
                        />
                        {/* Render selections relative to the image center */}
                        {/* FIX: Corrected invalid function-as-child syntax to a standard conditional render. */}
                        {image && <>
                           {ocrSelection && (
                            <div
                                className="absolute border-2 border-cyan-400 bg-cyan-400 bg-opacity-20 pointer-events-none"
                                style={{
                                    left: ocrSelection.x - (image.naturalWidth / 2),
                                    top: ocrSelection.y - (image.naturalHeight / 2),
                                    width: ocrSelection.width,
                                    height: ocrSelection.height,
                                }}
                            />
                           )}
                           {selection && (
                            <div
                                className="absolute border-2 border-yellow-400 pointer-events-none"
                                style={{
                                    left: selection.x - (image.naturalWidth / 2),
                                    top: selection.y - (image.naturalHeight / 2),
                                    width: selection.width,
                                    height: selection.height,
                                }}
                            />
                           )}
                        </>}
                    </div>
                     {/* Live drawing selection in screen-space */}
                    {drawingSelection && (
                      <div
                          className="absolute border-2 border-dashed border-yellow-400 bg-yellow-400 bg-opacity-25"
                          style={{
                              left: drawingSelection.x,
                              top: drawingSelection.y,
                              width: drawingSelection.width,
                              height: drawingSelection.height,
                          }}
                      />
                    )}
                </>
            )}
            {!currentImage && <div className="flex items-center justify-center h-full text-gray-500">No images loaded.</div>}
        </div>
    );
});


const DataEntryPanel = memo(function DataEntryPanel({ 
    record, 
    onCommitChange, 
    ocrText, 
    isOcrLoading, 
    selection, 
    onRunOCR,
    onAutoParse,
    isParsing,
    onNavigateImage,
    currentImageIndex,
    headstoneFileCount,
    onUndo,
    canUndo,
    onRedo,
    canRedo,
    onSave,
    onExport,
    onUpdateStatus,
    onUploadStreetViewPhoto,
    onRemoveStreetViewPhoto,
    onGetGpsFromImage,
} : {
    record: CemeteryRecord | null,
    onCommitChange: (record: CemeteryRecord) => void,
    ocrText: string,
    isOcrLoading: boolean,
    selection: SelectionRect | null,
    onRunOCR: () => void,
    onAutoParse: () => void,
    isParsing: boolean,
    onNavigateImage: (direction: number) => void,
    currentImageIndex: number,
    headstoneFileCount: number,
    onUndo: () => void,
    canUndo: boolean,
    onRedo: () => void,
    canRedo: boolean,
    onSave: () => void,
    onExport: () => void,
    onUpdateStatus: (msg: string, duration?: number) => void,
    onUploadStreetViewPhoto: (file: File) => void;
    onRemoveStreetViewPhoto: () => void;
    onGetGpsFromImage: () => void;
}) {
    const [localRecord, setLocalRecord] = useState(record);
    const [debouncedCommit, cancelDebounce] = useDebouncedCallback(onCommitChange, 500);
    const streetViewFileInputRef = useRef<HTMLInputElement>(null);


    // Sync authoritative `record` prop from parent to local state.
    // This is the single point of entry for external updates (undo, next image, auto-fill).
    // It cancels any pending debounced updates to prevent overwriting the authoritative state.
    useEffect(() => {
        cancelDebounce();
        setLocalRecord(record);
    }, [record, cancelDebounce]);

    // Handlers update local state immediately for responsiveness and schedule a debounced update to the parent.
    const handleFieldChange = useCallback((field: keyof Omit<CemeteryRecord, 'people' | 'ocrOptions' | 'gpsCoordinates'>, value: any) => {
        setLocalRecord(prev => {
            if (!prev) return null;
            const newRecord = { ...prev, [field]: value };
            debouncedCommit(newRecord);
            return newRecord;
        });
    }, [debouncedCommit]);
    
    const handleGpsChange = useCallback((field: 'latitude' | 'longitude', value: string) => {
        setLocalRecord(prev => {
            if (!prev) return null;
            const newRecord = { 
                ...prev, 
                gpsCoordinates: { ...prev.gpsCoordinates, [field]: value } 
            };
            debouncedCommit(newRecord);
            return newRecord;
        });
    }, [debouncedCommit]);

    const handleOcrOptionChange = useCallback((field: keyof OcrOptions, value: string) => {
        setLocalRecord(prev => {
            if (!prev) return null;
            const newRecord = { ...prev, ocrOptions: { ...prev.ocrOptions, [field]: value } };
            debouncedCommit(newRecord);
            return newRecord;
        });
    }, [debouncedCommit]);
    
    const handlePersonChange = useCallback((index: number, field: keyof Omit<Person, 'id'>, value: string) => {
        setLocalRecord(prev => {
            if (!prev) return null;
            const newPeople = [...prev.people];
            newPeople[index] = { ...newPeople[index], [field]: value };
            const newRecord = { ...prev, people: newPeople };
            debouncedCommit(newRecord);
            return newRecord;
        });
    }, [debouncedCommit]);

    // For structural changes, commit immediately to the parent to avoid state inconsistencies.
    const addPerson = useCallback(() => {
        if (!record) return;
        cancelDebounce(); // Cancel any pending debounced text edits.
        const newPerson: Person = { id: crypto.randomUUID(), firstName: '', middleName: '', lastName: '', born: '', died: '' };
        const updatedRecord = { ...record, people: [...record.people, newPerson] };
        onCommitChange(updatedRecord);
    }, [record, onCommitChange, cancelDebounce]);

    const removePerson = useCallback((id: string) => {
        if (!record || record.people.length <= 1) return;
        cancelDebounce();
        const updatedRecord = { ...record, people: record.people.filter(p => p.id !== id) };
        onCommitChange(updatedRecord);
    }, [record, onCommitChange, cancelDebounce]);

    const isOcrReadyForParsing = ocrText && !isOcrLoading && !ocrText.startsWith('OCR Failed:') && ocrText !== 'Running OCR...';

    // Proxy click handler to cancel any pending state updates before triggering auto-fill.
    const handleAutoParseClick = useCallback(() => {
        cancelDebounce();
        onAutoParse();
    }, [cancelDebounce, onAutoParse]);

    const handleStreetViewUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            onUploadStreetViewPhoto(e.target.files[0]);
        }
        // Reset file input to allow uploading the same file again
        e.target.value = '';
    };

    return (
        <div className="col-span-12 md:col-span-4 flex flex-col gap-4 overflow-hidden">
            <Panel className="flex-shrink-0 flex flex-col gap-2">
                <div className="flex gap-2">
                    <Button onClick={onRunOCR} disabled={isOcrLoading || !selection} className="flex-1">
                        {isOcrLoading ? 'Processing...' : 'Run OCR'}
                    </Button>
                     <Button onClick={handleAutoParseClick} disabled={!isOcrReadyForParsing || isParsing} className="flex-1" variant="primary">
                        {isParsing ? 'Analyzing...' : '[Auto-Parse with AI]'}
                    </Button>
                </div>
                <details className="mt-1">
                    <summary className="cursor-pointer text-sm text-gray-400 hover:text-white select-none">
                        Advanced OCR Options
                    </summary>
                    <div className="mt-2 p-3 bg-gray-800 rounded-md space-y-3">
                        <fieldset disabled={!localRecord}>
                            {/* OCR Mode Select */}
                            <div>
                                <label htmlFor="ocr-mode" className="block text-xs font-medium text-gray-300 mb-1">Processing Mode</label>
                                <select id="ocr-mode" value={localRecord?.ocrOptions.mode || 'standard'} onChange={e => handleOcrOptionChange('mode', e.target.value)} className="w-full bg-gray-700 border border-gray-600 rounded-md p-1.5 text-sm focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500">
                                    <option value="standard">Standard Text</option>
                                    <option value="handwritten">Handwritten / Faded</option>
                                    <option value="damaged">Damaged / Weathered Stone</option>
                                </select>
                            </div>
                             {/* Other OCR Inputs */}
                            <div>
                                <label htmlFor="custom-prompt" className="block text-xs font-medium text-gray-300 mb-1">Custom Instructions</label>
                                <input id="custom-prompt" type="text" value={localRecord?.ocrOptions.customPrompt || ''} onChange={e => handleOcrOptionChange('customPrompt', e.target.value)} placeholder="e.g., 'focus on the bottom half'" className="w-full bg-gray-700 border border-gray-600 rounded-md p-1.5 text-sm focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"/>
                            </div>
                            <div>
                                <label htmlFor="ocr-language" className="block text-xs font-medium text-gray-300 mb-1">Language</label>
                                <input id="ocr-language" type="text" value={localRecord?.ocrOptions.language || ''} onChange={e => handleOcrOptionChange('language', e.target.value)} placeholder="e.g., 'English'" className="w-full bg-gray-700 border border-gray-600 rounded-md p-1.5 text-sm focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"/>
                            </div>
                            <div>
                                <label htmlFor="ocr-charset" className="block text-xs font-medium text-gray-300 mb-1">Allowed Characters</label>
                                <input id="ocr-charset" type="text" value={localRecord?.ocrOptions.characterSet || ''} onChange={e => handleOcrOptionChange('characterSet', e.target.value)} placeholder="e.g., 'A-Z 0-9 -'" className="w-full bg-gray-700 border border-gray-600 rounded-md p-1.5 text-sm focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"/>
                            </div>
                            <div>
                                <label htmlFor="ocr-negative-prompt" className="block text-xs font-medium text-gray-300 mb-1">Negative Prompt (Ignore)</label>
                                <input id="ocr-negative-prompt" type="text" value={localRecord?.ocrOptions.negativePrompt || ''} onChange={e => handleOcrOptionChange('negativePrompt', e.target.value)} placeholder="e.g., 'ignore all dates'" className="w-full bg-gray-700 border border-gray-600 rounded-md p-1.5 text-sm focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"/>
                            </div>
                        </fieldset>
                    </div>
                </details>
            </Panel>
            <Panel className="flex-1 flex flex-col gap-4 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-800">
                {localRecord ? (
                    <>
                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-1">Plot Location</label>
                            <input type="text" value={localRecord.plotLocation} onChange={e => handleFieldChange('plotLocation', e.target.value)} className="w-full bg-gray-800 border border-gray-600 rounded-md p-2 focus:ring-indigo-500 focus:border-indigo-500"/>
                        </div>
                        <div className="flex gap-2 items-end">
                            <div className="flex-grow">
                                <label className="block text-sm font-medium text-gray-300 mb-1">GPS Latitude</label>
                                <input type="text" placeholder="e.g., 40.7128" value={localRecord.gpsCoordinates?.latitude || ''} onChange={e => handleGpsChange('latitude', e.target.value)} className="w-full bg-gray-800 border border-gray-600 rounded-md p-2 focus:ring-indigo-500 focus:border-indigo-500"/>
                            </div>
                             <div className="flex-grow">
                                <label className="block text-sm font-medium text-gray-300 mb-1">GPS Longitude</label>
                                <input type="text" placeholder="e.g., -74.0060" value={localRecord.gpsCoordinates?.longitude || ''} onChange={e => handleGpsChange('longitude', e.target.value)} className="w-full bg-gray-800 border border-gray-600 rounded-md p-2 focus:ring-indigo-500 focus:border-indigo-500"/>
                            </div>
                            <Button onClick={onGetGpsFromImage} variant="secondary" className="h-[2.625rem] px-3" title="Get GPS from image metadata (EXIF)">Get</Button>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-1">360° Photo</label>
                            <div className="flex gap-2 items-center">
                                <span className="flex-grow bg-gray-800 border border-gray-600 rounded-md p-2 text-sm truncate text-gray-300" title={localRecord.streetViewPhotoFilename || ''}>
                                    {localRecord.streetViewPhotoFilename || 'No photo uploaded.'}
                                </span>
                                <input type="file" accept="image/jpeg,image/png" ref={streetViewFileInputRef} onChange={handleStreetViewUpload} className="hidden" />
                                <Button onClick={() => streetViewFileInputRef.current?.click()} variant="secondary" className="px-3">Upload</Button>
                                <Button onClick={onRemoveStreetViewPhoto} variant="danger" disabled={!localRecord.streetViewPhotoFilename} className="px-3">
                                   <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm4 0a1 1 0 012 0v6a1 1 0 11-2 0V8z" clipRule="evenodd" /></svg>
                                </Button>
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-1">Epitaph</label>
                            <textarea value={localRecord.epitaph} onChange={e => handleFieldChange('epitaph', e.target.value)} rows={4} className="w-full bg-gray-800 border border-gray-600 rounded-md p-2 focus:ring-indigo-500 focus:border-indigo-500"/>
                        </div>
                        <hr className="border-gray-600"/>
                        <h3 className="text-lg font-semibold text-indigo-400">Individuals on this Plot</h3>
                        {localRecord.people.map((person, index) => (
                            <div key={person.id} className="p-3 bg-gray-800 rounded-md space-y-2 relative">
                                {localRecord.people.length > 1 && (
                                    <button onClick={() => removePerson(person.id)} className="absolute top-1 right-1 text-gray-400 hover:text-red-500 text-xl leading-none">&times;</button>
                                )}
                                <div className="flex gap-2">
                                    <input type="text" placeholder="First Name" value={person.firstName} onChange={e => handlePersonChange(index, 'firstName', e.target.value)} onBlur={e => handlePersonChange(index, 'firstName', capitalizeName(e.target.value))} className="w-1/3 bg-gray-700 border border-gray-600 rounded-md p-2"/>
                                    <input type="text" placeholder="Middle Name" value={person.middleName} onChange={e => handlePersonChange(index, 'middleName', e.target.value)} onBlur={e => handlePersonChange(index, 'middleName', capitalizeName(e.target.value))} className="w-1/3 bg-gray-700 border border-gray-600 rounded-md p-2"/>
                                    <input type="text" placeholder="Last Name" value={person.lastName} onChange={e => handlePersonChange(index, 'lastName', e.target.value)} onBlur={e => handlePersonChange(index, 'lastName', capitalizeName(e.target.value))} className="w-1/3 bg-gray-700 border border-gray-600 rounded-md p-2"/>
                                </div>
                                <div className="flex gap-2">
                                    <input type="text" placeholder="Born" value={person.born} onChange={e => handlePersonChange(index, 'born', e.target.value)} className="w-1/2 bg-gray-700 border border-gray-600 rounded-md p-2"/>
                                    <input type="text" placeholder="Died" value={person.died} onChange={e => handlePersonChange(index, 'died', e.target.value)} className="w-1/2 bg-gray-700 border border-gray-600 rounded-md p-2"/>
                                </div>
                            </div>
                        ))}
                        <Button onClick={addPerson} variant="secondary">[+ Add Person]</Button>
                        <hr className="border-gray-600"/>
                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-1">OCR Output (read-only)</label>
                            <textarea readOnly value={ocrText} rows={6} className="w-full bg-gray-900 border border-gray-600 rounded-md p-2 font-mono text-sm"/>
                        </div>
                    </>
                ) : (
                   <div className="flex items-center justify-center h-full text-gray-500">Select an image to enter data.</div>
                )}
            </Panel>
            <Panel className="flex-shrink-0 flex flex-col gap-2">
                <div className="flex gap-2">
                    <Button onClick={() => onNavigateImage(-1)} disabled={currentImageIndex <= 0} className="flex-1" variant="secondary">Previous Image</Button>
                    <Button onClick={() => onNavigateImage(1)} disabled={currentImageIndex >= headstoneFileCount - 1} className="flex-1" variant="secondary">Next Image</Button>
                </div>
                <div className="flex gap-2">
                    <Button onClick={onUndo} disabled={!canUndo} className="flex-1" variant="secondary">Undo Data</Button>
                    <Button onClick={onRedo} disabled={!canRedo} className="flex-1" variant="secondary">Redo Data</Button>
                </div>
                <Button onClick={onSave} className="w-full">Save Record</Button>
                <Button onClick={onExport} variant="primary" className="bg-green-600 hover:bg-green-700 focus:ring-green-500">Export All to CSV</Button>
            </Panel>
        </div>
    );
});

const MapPanel = memo(function MapPanel({
    isVisible,
    records,
    currentRecord,
    onMapInteraction,
    onMarkerClick,
    onUpdateStatus,
    onStreetViewClick,
    hasCustomStreetView
}: {
    isVisible: boolean;
    records: Map<string, CemeteryRecord>;
    currentRecord: CemeteryRecord | null;
    onMapInteraction: (coords: { lat: number; lng: number }) => void;
    onMarkerClick: (filename: string) => void;
    onUpdateStatus: (msg: string, duration?: number) => void;
    onStreetViewClick: () => void;
    hasCustomStreetView: boolean;
}) {
    const mapContainerRef = useRef<HTMLDivElement>(null);
    const mapRef = useRef<L.Map | null>(null);
    const markersRef = useRef<{ [key: string]: L.Marker }>({});
    const [searchQuery, setSearchQuery] = useState('');
    
    // HACK: Need to check if Leaflet is loaded on the window object before using it.
    const L = (window as any).L;

    const hasValidGpsCoords = useMemo(() => {
        if (!currentRecord?.gpsCoordinates) return false;
        const lat = parseFloat(currentRecord.gpsCoordinates.latitude);
        const lng = parseFloat(currentRecord.gpsCoordinates.longitude);
        return !isNaN(lat) && !isNaN(lng);
    }, [currentRecord]);

    const isStreetViewEnabled = hasCustomStreetView || hasValidGpsCoords;

    const handleSearch = async (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!searchQuery.trim() || !mapRef.current) return;
        
        onUpdateStatus(`Searching for "${searchQuery}"...`, 3000);

        try {
            const response = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchQuery)}&limit=1`);
            if (!response.ok) {
                throw new Error('Network response was not ok.');
            }
            const data = await response.json();

            if (data && data.length > 0) {
                const { lat, lon, display_name } = data[0];
                const newLat = parseFloat(lat);
                const newLng = parseFloat(lon);
                mapRef.current.setView([newLat, newLng], 15);
                onUpdateStatus(`Found: ${display_name}`, 5000);
            } else {
                onUpdateStatus(`Could not find location: "${searchQuery}"`, 5000);
            }
        } catch (error) {
            console.error("Geocoding search failed:", error);
            onUpdateStatus("Map search failed. Please check your connection.", 5000);
        }
    };


    // Initialize map
    useEffect(() => {
        if (!L || !isVisible || !mapContainerRef.current || mapRef.current) return;

        mapRef.current = L.map(mapContainerRef.current).setView([40.7128, -74.0060], 13); // Default to NYC

        const streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(mapRef.current);

        const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
        });

        const topoLayer = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
            attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)'
        });

        const baseMaps = {
            "Street": streetLayer,
            "Satellite": satelliteLayer,
            "Topographical": topoLayer
        };

        L.control.layers(baseMaps).addTo(mapRef.current);
        
        mapRef.current.on('click', (e: L.LeafletMouseEvent) => {
            onMapInteraction({ lat: e.latlng.lat, lng: e.latlng.lng });
        });

        return () => { // Cleanup on unmount or visibility change
            if (mapRef.current) {
                mapRef.current.remove();
                mapRef.current = null;
            }
        };
    }, [isVisible, L, onMapInteraction]);

    // Update markers based on records
    useEffect(() => {
        if (!L || !mapRef.current) return;

        const map = mapRef.current;
        const currentMarkers = { ...markersRef.current };
        const recordsWithGps: string[] = [];
        
        // Add/update markers
        records.forEach((record) => {
            const isCurrent = record.imageFilename === currentRecord?.imageFilename;
            
            // Use live coordinates from the currentRecord prop for the active marker to ensure immediate feedback.
            // Otherwise, use the saved coordinates from the main records map.
            const sourceCoords = (isCurrent && currentRecord) ? currentRecord.gpsCoordinates : record.gpsCoordinates;
            
            const { latitude, longitude } = sourceCoords;
            const lat = parseFloat(latitude);
            const lng = parseFloat(longitude);

            if (!isNaN(lat) && !isNaN(lng)) {
                recordsWithGps.push(record.imageFilename);

                const icon = L.divIcon({
                  className: '', // Use empty class, let HTML define visuals
                  html: `<div class="relative w-8 h-8">
                            ${isCurrent ? '<div class="absolute top-0 left-0 w-full h-full rounded-full bg-indigo-400 opacity-75 animate-ping"></div>' : ''}
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="relative w-full h-full drop-shadow-lg ${isCurrent ? 'text-indigo-500' : 'text-gray-500'}" fill="currentColor"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
                         </div>`,
                  iconSize: [32, 32],
                  iconAnchor: [16, 32]
                });
                
                const person = record.people[0];
                const personName = person ? `${person.firstName} ${person.lastName}`.trim() : '';
                const plotName = record.plotLocation;
                let tooltipText = '';

                if (personName && plotName) {
                    tooltipText = `<b>${personName}</b><br>${plotName}`;
                } else {
                    tooltipText = personName || plotName || 'Unnamed Plot';
                }


                if (currentMarkers[record.imageFilename]) { // Update existing
                    const marker = currentMarkers[record.imageFilename];
                    marker.setLatLng([lat, lng]);
                    marker.setIcon(icon);
                    marker.setZIndexOffset(isCurrent ? 1000 : 0);

                    if (marker.getTooltip()?.getContent() !== tooltipText) {
                        marker.setTooltipContent(tooltipText);
                    }
                    
                    // Use the official Leaflet API to enable/disable dragging.
                    if (isCurrent) {
                        if (marker.dragging) marker.dragging.enable();
                    } else {
                        if (marker.dragging) marker.dragging.disable();
                    }
                } else { // Create new
                    const marker = L.marker([lat, lng], {
                        icon: icon,
                        draggable: isCurrent,
                        autoPan: true,
                        zIndexOffset: isCurrent ? 1000 : 0
                    }).addTo(map);

                    marker.on('click', () => onMarkerClick(record.imageFilename));
                    marker.on('dragend', (e) => onMapInteraction(e.target.getLatLng()));
                    marker.bindTooltip(tooltipText);
                    
                    currentMarkers[record.imageFilename] = marker;
                }
            }
        });
        
        // Remove stale markers
        Object.keys(currentMarkers).forEach(filename => {
            if (!recordsWithGps.includes(filename)) {
                currentMarkers[filename].remove();
                delete currentMarkers[filename];
            }
        });
        
        markersRef.current = currentMarkers;

    }, [records, currentRecord, L, onMapInteraction, onMarkerClick]);

     // Pan map to current record
    useEffect(() => {
        if (!mapRef.current || !currentRecord) return;
        const { latitude, longitude } = currentRecord.gpsCoordinates;
        const lat = parseFloat(latitude);
        const lng = parseFloat(longitude);
        if (!isNaN(lat) && !isNaN(lng)) {
            mapRef.current.setView([lat, lng], mapRef.current.getZoom(), { animate: true });
        }
    }, [currentRecord]);


    return (
        <aside className={`transition-all duration-300 ease-in-out bg-gray-900 shadow-2xl overflow-hidden ${isVisible ? 'w-1/4 p-4' : 'w-0 p-0'}`}>
            <div className="flex flex-col h-full min-w-[300px]">
                <h2 className="text-xl font-bold mb-2 text-indigo-400">Interactive Map</h2>
                 <div className="flex items-center gap-2 mb-4">
                    <form onSubmit={handleSearch} className="flex-grow">
                        <div className="relative">
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={e => setSearchQuery(e.target.value)}
                                placeholder="Search for a location..."
                                className="w-full bg-gray-800 border border-gray-600 rounded-md p-2 pr-10 focus:ring-indigo-500 focus:border-indigo-500"
                                aria-label="Map location search"
                            />
                            <button type="submit" className="absolute top-1/2 right-2 -translate-y-1/2 text-gray-400 hover:text-white" aria-label="Search">
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                    <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
                                </svg>
                            </button>
                        </div>
                    </form>
                    <button
                        onClick={onStreetViewClick}
                        disabled={!isStreetViewEnabled}
                        title={hasCustomStreetView ? "View custom 360° photo" : (hasValidGpsCoords ? "Open Google Street View" : "No GPS data")}
                        className="p-2 h-[2.625rem] bg-gray-600 rounded-md hover:bg-gray-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        aria-label="Open Street View"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" className={`h-5 w-5 ${hasCustomStreetView ? 'text-cyan-300' : 'text-white'}`} viewBox="0 0 24 24" fill="currentColor">
                           <path d="M12 2c1.1 0 2 .9 2 2s-.9 2-2 2-2-.9-2-2 .9-2 2-2zm9 7h-6v13h-2v-6h-2v6H9V9H3V7h18v2z"></path>
                        </svg>
                    </button>
                </div>
                <div 
                    ref={mapContainerRef}
                    className="flex-grow bg-gray-800 rounded-lg"
                    id="map"
                >
                  {!L && <div className="flex items-center justify-center h-full text-gray-500">Loading map...</div>}
                </div>
            </div>
        </aside>
    );
});

const ProgressModal = memo(function ProgressModal({ progress, onCancel }: {
    progress: { current: number; total: number; step: string; filename: string; } | null;
    onCancel: () => void;
}) {
    if (!progress) return null;

    const percent = progress.total > 0 ? (progress.current / progress.total) * 100 : 0;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
            <div className="bg-gray-800 rounded-lg shadow-2xl p-8 w-full max-w-md text-center">
                <h2 className="text-2xl font-bold text-indigo-400 mb-4">Autonomous Batch Processing</h2>
                <p className="text-gray-300 mb-2">Processing file {progress.current} of {progress.total}:</p>
                <p className="font-mono text-sm text-amber-400 truncate mb-4" title={progress.filename}>{progress.filename}</p>
                <div className="w-full bg-gray-700 rounded-full h-2.5 mb-4">
                    <div className="bg-indigo-600 h-2.5 rounded-full" style={{ width: `${percent}%` }}></div>
                </div>
                <p className="text-lg text-gray-200 mb-6">Current Step: <span className="font-semibold">{progress.step}</span></p>
                <Button onClick={onCancel} variant="danger">Cancel Batch</Button>
            </div>
        </div>
    );
});

const ReviewPanel = memo(function ReviewPanel({
    isVisible,
    results,
    onSelect,
    onClose
} : {
    isVisible: boolean;
    results: BatchProcessResult[];
    onSelect: (filename: string) => void;
    onClose: () => void;
}) {
    const statusStyles = {
        success: { icon: '✓', color: 'text-green-400', bg: 'bg-green-900' },
        partial: { icon: '!', color: 'text-yellow-400', bg: 'bg-yellow-900' },
        error: { icon: '✖', color: 'text-red-400', bg: 'bg-red-900' },
    };

    const getPrimaryName = (record?: CemeteryRecord) => {
        if (!record || record.people.length === 0) return 'No Name Found';
        const person = record.people[0];
        return `${person.firstName} ${person.lastName}`.trim() || 'Unnamed';
    };

    return (
        <aside className={`transition-all duration-300 ease-in-out bg-gray-900 shadow-2xl overflow-hidden ${isVisible ? 'w-1/4 p-4' : 'w-0 p-0'}`}>
            <div className="flex flex-col h-full min-w-[300px]">
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-xl font-bold text-indigo-400">Batch Review</h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-white text-2xl leading-none">&times;</button>
                </div>
                {results.length === 0 ? (
                    <div className="flex-grow flex items-center justify-center text-gray-500 text-center px-4">
                        No batch results to display. Run an autonomous batch to populate this list.
                    </div>
                ) : (
                    <div className="flex-grow overflow-y-auto space-y-2 scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-800 pr-2">
                        {results.map(({ status, imageFilename, record, errorMessage }) => {
                            const { icon, color, bg } = statusStyles[status];
                            const title = `Status: ${status}\nFile: ${imageFilename}${errorMessage ? `\nError: ${errorMessage}` : ''}`;
                            return (
                                <div
                                    key={imageFilename}
                                    onClick={() => onSelect(imageFilename)}
                                    className={`flex items-center p-2 rounded-md cursor-pointer transition-colors ${bg} bg-opacity-40 hover:bg-opacity-70 border border-gray-700`}
                                    title={title}
                                >
                                    <div className={`w-8 h-8 flex-shrink-0 rounded-full flex items-center justify-center mr-3 font-bold text-lg ${color} ${bg}`}>
                                        {icon}
                                    </div>
                                    <div className="flex-grow truncate">
                                        <p className="font-semibold truncate">{getPrimaryName(record)}</p>
                                        <p className="text-xs text-gray-400 truncate">{imageFilename}</p>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </aside>
    );
});


const SettingsModal = memo(function SettingsModal({
    isOpen,
    onClose,
    settings,
    onSave
} : {
    isOpen: boolean;
    onClose: () => void;
    settings: AiSettings;
    onSave: (settings: AiSettings) => void;
}) {
    if (!isOpen) return null;
    
    const localConnector = useMemo(() => new LocalServiceConnector(), []);
    const [localSettings, setLocalSettings] = useState(settings);
    const [testStatuses, setTestStatuses] = useState({
        parsing: { testing: false, message: '', success: null as boolean | null },
        ocr: { testing: false, message: '', success: null as boolean | null },
        imageGen: { testing: false, message: '', success: null as boolean | null },
    });
    
    // Reset local state when modal opens
    useEffect(() => {
        setLocalSettings(settings);
        setTestStatuses({
            parsing: { testing: false, message: '', success: null },
            ocr: { testing: false, message: '', success: null },
            imageGen: { testing: false, message: '', success: null },
        });
    }, [isOpen, settings]);

    const handleProviderChange = (key: keyof AiSettings, value: AiParsingProvider | AiOcrProvider) => {
        setLocalSettings(prev => ({ ...prev, [key]: value }));
    };
    
    const handleLocalOcrChange = (field: keyof LocalOcrSettings, value: string) => {
        setLocalSettings(prev => ({
            ...prev,
            localOcr: { ...prev.localOcr, [field]: value }
        }));
    };

    type TestType = keyof typeof testStatuses;
    const handleTestConnection = async (type: TestType) => {
        setTestStatuses(prev => ({ ...prev, [type]: { testing: true, message: 'Pinging server...', success: null } }));
        
        let result: { success: boolean, message: string };
        switch (type) {
            case 'parsing':
                result = await localConnector.testConnection();
                break;
            case 'ocr':
                result = await localConnector.testOcrConnection(localSettings.localOcr);
                break;
            case 'imageGen':
                result = await localConnector.testImageGenConnection();
                break;
            default:
                return;
        }

        setTestStatuses(prev => ({ ...prev, [type]: { testing: false, message: result.message, success: result.success } }));
    };

    const StatusMessage: React.FC<{ status: typeof testStatuses[TestType] }> = ({ status }) => {
        if (!status.message) return null;
        const color = status.success === true ? 'text-green-400' : status.success === false ? 'text-red-400' : 'text-gray-400';
        return <span className={`text-sm font-medium ${color}`}>{status.message}</span>;
    };


    return (
        <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50" onClick={onClose}>
            <div className="bg-gray-800 rounded-lg shadow-2xl p-8 w-full max-w-2xl text-left" onClick={e => e.stopPropagation()}>
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-2xl font-bold text-indigo-400">AI Configuration</h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-white text-3xl leading-none">&times;</button>
                </div>

                <div className="space-y-6">
                    {/* PARSING PROVIDER */}
                    <div>
                        <label className="block text-lg font-medium text-gray-200 mb-2">Parsing Provider</label>
                        <p className="text-sm text-gray-400 mb-3">Service for the "[Auto-Parse with AI]" feature, which structures OCR text into data fields.</p>
                        <div className="space-y-2 rounded-md bg-gray-900 p-3">
                            <label className="flex items-center gap-3 p-2 rounded-md hover:bg-gray-700 cursor-pointer">
                                <input type="radio" name="parsing-provider" value="google-ai" checked={localSettings.parsing === 'google-ai'} onChange={() => handleProviderChange('parsing', 'google-ai')} className="form-radio h-5 w-5 text-indigo-600 bg-gray-700 border-gray-600 focus:ring-indigo-500" />
                                <span>
                                    <span className="font-semibold">Google AI (Cloud)</span>
                                    <span className="block text-xs text-gray-400">Uses the Gemini model. Requires a configured API Key.</span>
                                </span>
                            </label>
                            <label className="flex items-center gap-3 p-2 rounded-md hover:bg-gray-700 cursor-pointer">
                                <input type="radio" name="parsing-provider" value="lm-studio" checked={localSettings.parsing === 'lm-studio'} onChange={() => handleProviderChange('parsing', 'lm-studio')} className="form-radio h-5 w-5 text-indigo-600 bg-gray-700 border-gray-600 focus:ring-indigo-500" />
                                <span>
                                    <span className="font-semibold">LM Studio (Local)</span>
                                    <span className="block text-xs text-gray-400">Connects to a local model via LM Studio's server (http://127.0.0.1:1234).</span>
                                </span>
                            </label>
                             {localSettings.parsing === 'lm-studio' && (
                                <div className="mt-3 ml-10 p-3 bg-gray-800 rounded-md">
                                     <div className="flex items-center gap-3">
                                        <Button onClick={() => handleTestConnection('parsing')} variant="secondary" disabled={testStatuses.parsing.testing}>
                                            {testStatuses.parsing.testing ? 'Testing...' : 'Test Connection'}
                                        </Button>
                                        <StatusMessage status={testStatuses.parsing} />
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* OCR PROVIDER */}
                    <div>
                        <label className="block text-lg font-medium text-gray-200 mb-2">OCR Provider</label>
                        <p className="text-sm text-gray-400 mb-3">Service for the "Run OCR" feature, which extracts raw text from an image selection.</p>
                         <div className="space-y-2 rounded-md bg-gray-900 p-3">
                            <label className="flex items-center gap-3 p-2 rounded-md hover:bg-gray-700 cursor-pointer">
                                <input type="radio" name="ocr-provider" value="google-ai" checked={localSettings.ocr === 'google-ai'} onChange={() => handleProviderChange('ocr', 'google-ai')} className="form-radio h-5 w-5 text-indigo-600 bg-gray-700 border-gray-600 focus:ring-indigo-500" />
                                <span>
                                    <span className="font-semibold">Google AI (Cloud)</span>
                                    <span className="block text-xs text-gray-400">High-accuracy OCR using the Gemini vision model.</span>
                                </span>
                            </label>
                            <label className="flex items-center gap-3 p-2 rounded-md hover:bg-gray-700 cursor-pointer">
                                <input type="radio" name="ocr-provider" value="local-ocr" checked={localSettings.ocr === 'local-ocr'} onChange={() => handleProviderChange('ocr', 'local-ocr')} className="form-radio h-5 w-5 text-indigo-600 bg-gray-700 border-gray-600 focus:ring-indigo-500" />
                                <span>
                                    <span className="font-semibold">Local OCR Service</span>
                                    <span className="block text-xs text-gray-400">Connect to a self-hosted OCR engine.</span>
                                </span>
                            </label>
                            {localSettings.ocr === 'local-ocr' && (
                                <div className="mt-3 ml-10 p-3 bg-gray-800 rounded-md space-y-3">
                                    <div>
                                        <label htmlFor="ocr-url" className="block text-xs font-medium text-gray-300 mb-1">Server URL</label>
                                        <input
                                            id="ocr-url"
                                            type="text"
                                            value={localSettings.localOcr.url}
                                            onChange={e => handleLocalOcrChange('url', e.target.value)}
                                            placeholder="http://localhost:5000/v1/ocr/image-to-text"
                                            className="w-full bg-gray-700 border border-gray-600 rounded-md p-1.5 text-sm focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
                                        />
                                    </div>
                                    <div>
                                        <label htmlFor="ocr-key" className="block text-xs font-medium text-gray-300 mb-1">API Key (Optional)</label>
                                        <input
                                            id="ocr-key"
                                            type="password"
                                            value={localSettings.localOcr.apiKey || ''}
                                            onChange={e => handleLocalOcrChange('apiKey', e.target.value)}
                                            placeholder="Enter API key if required"
                                            className="w-full bg-gray-700 border border-gray-600 rounded-md p-1.5 text-sm focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
                                        />
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <Button onClick={() => handleTestConnection('ocr')} variant="secondary" disabled={testStatuses.ocr.testing}>
                                            {testStatuses.ocr.testing ? 'Testing...' : 'Test Connection'}
                                        </Button>
                                        <StatusMessage status={testStatuses.ocr} />
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                    
                    {/* IMAGE GENERATION */}
                    <div>
                        <label className="block text-lg font-medium text-gray-200 mb-2">Local Image Generation</label>
                        <div className="rounded-md bg-gray-900 p-4 space-y-3">
                           <p className="text-sm text-gray-400">The "Creative Assistant" feature uses a local image generation server (like Stable Diffusion AUTOMATIC1111) at http://localhost:7860.</p>
                           <div className="flex items-center gap-3">
                                <Button onClick={() => handleTestConnection('imageGen')} variant="secondary" disabled={testStatuses.imageGen.testing}>
                                    {testStatuses.imageGen.testing ? 'Testing...' : 'Test Connection'}
                                </Button>
                                <StatusMessage status={testStatuses.imageGen} />
                            </div>
                        </div>
                    </div>
                </div>

                <div className="mt-8 flex justify-end gap-3">
                    <Button onClick={onClose} variant="secondary">Cancel</Button>
                    <Button onClick={() => onSave(localSettings)}>Save Settings</Button>
                </div>
            </div>
        </div>
    );
});

const ImageGenerationPanel = memo(function ImageGenerationPanel({
    currentRecord,
    isGenerating,
    generatedImage,
    onGenerate,
}: {
    currentRecord: CemeteryRecord | null;
    isGenerating: boolean;
    generatedImage: string | null;
    onGenerate: (prompt: string) => void;
}) {
    const [prompt, setPrompt] = useState('');

    const generateDefaultPrompt = useCallback(() => {
        if (!currentRecord) return;
        const person = currentRecord.people[0];
        if (!person) return;
        
        const name = `${person.firstName} ${person.lastName}`.trim();
        let newPrompt = `Concept art for a memorial headstone in a peaceful, sunlit cemetery.`;
        if (name) {
            newPrompt += ` The name on the stone is "${name}".`;
        }
        if (person.born && person.died) {
            newPrompt += ` Dates: ${person.born} - ${person.died}.`;
        }
        if (currentRecord.epitaph) {
            newPrompt += ` Epitaph includes the words "${currentRecord.epitaph.slice(0, 50)}".`;
        }
        newPrompt += ` Style: digital painting, high detail, atmospheric lighting.`
        setPrompt(newPrompt);
    }, [currentRecord]);

    return (
        <Panel className="flex-shrink-0 flex flex-col gap-4">
            <h3 className="text-lg font-semibold text-indigo-400">Creative Assistant (Local Image Generation)</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="flex flex-col gap-2">
                    <textarea 
                        value={prompt}
                        onChange={e => setPrompt(e.target.value)}
                        placeholder="Describe a headstone concept... e.g., 'A granite headstone with an engraved ship, for John Doe, 1880-1945'"
                        rows={5}
                        className="w-full bg-gray-800 border border-gray-600 rounded-md p-2 focus:ring-indigo-500 focus:border-indigo-500"
                        aria-label="Image generation prompt"
                    />
                    <div className="flex gap-2">
                        <Button onClick={generateDefaultPrompt} disabled={!currentRecord} variant="secondary" className="flex-1">Auto-fill Prompt</Button>
                        <Button onClick={() => onGenerate(prompt)} disabled={isGenerating || !prompt} className="flex-1">
                            {isGenerating ? 'Generating...' : 'Generate Concept'}
                        </Button>
                    </div>
                </div>
                <div className="bg-gray-900 rounded-md flex items-center justify-center p-2 aspect-square">
                    {isGenerating ? (
                        <div className="text-center text-gray-400">
                            <svg className="animate-spin h-8 w-8 mx-auto mb-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                            Generating...
                        </div>
                    ) : generatedImage ? (
                        <img src={generatedImage} alt="Generated concept art" className="max-w-full max-h-full object-contain rounded-md" />
                    ) : (
                        <div className="text-center text-gray-500">
                            Generated image will appear here.
                        </div>
                    )}
                </div>
            </div>
        </Panel>
    );
});


// --- Main App Component ---

export default function App() {
    // State
    const [isMapPanelVisible, setIsMapPanelVisible] = useState(false);
    const [isReviewPanelVisible, setIsReviewPanelVisible] = useState(false);
    const [isBatchRunning, setIsBatchRunning] = useState(false);
    const [batchProgress, setBatchProgress] = useState<{ current: number; total: number; step: string; filename: string } | null>(null);
    const [batchResults, setBatchResults] = useState<BatchProcessResult[]>([]);
    const cancelBatchRef = useRef(false);
    const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
    const [aiSettings, setAiSettings] = useState<AiSettings>(() => {
        const savedSettings = localStorage.getItem('aiSettings');
        const defaults: AiSettings = {
            parsing: 'google-ai',
            ocr: 'google-ai',
            localOcr: { url: 'http://localhost:5000/v1/ocr/image-to-text' },
        };
        try {
            if (savedSettings) {
                const parsed = JSON.parse(savedSettings);
                // Merge defaults with parsed to handle missing keys from older versions of settings.
                return { ...defaults, ...parsed, localOcr: { ...defaults.localOcr, ...(parsed.localOcr || {}) } };
            }
        } catch (e) {
            console.error("Failed to parse AI settings from localStorage", e);
        }
        return defaults;
    });
    
    const [headstoneFiles, setHeadstoneFiles] = useState<ImageFile[]>([]);
    const [streetViewPhotos, setStreetViewPhotos] = useState<Map<string, ImageFile>>(new Map());
    const [currentImageIndex, setCurrentImageIndex] = useState<number>(-1);
    
    const [records, setRecords] = useState<Map<string, CemeteryRecord>>(new Map());
    
    // History state for data entry form
    const {
        state: currentRecord,
        set: setCurrentRecord,
        undo: undoRecord,
        redo: redoRecord,
        canUndo: canUndoRecord,
        canRedo: canRedoRecord,
        reset: resetRecordHistory
    } = useHistoryState<CemeteryRecord | null>(null);
    
    // FIX: Add a ref to get the latest `currentRecord` inside callbacks without adding it as a dependency.
    // This helps stabilize callbacks and prevent race conditions.
    const currentRecordRef = useRef(currentRecord);
    useEffect(() => {
        currentRecordRef.current = currentRecord;
    }, [currentRecord]);


    // History state for image transformations
    const {
        state: transform,
        set: setTransformInHistory,
        undo: undoTransform,
        redo: redoTransform,
        canUndo: canUndoTransform,
        canRedo: canRedoTransform,
        reset: resetTransformHistory
    } = useHistoryState<TransformState>(INITIAL_TRANSFORM);

    // Live transform state for smooth panning/zooming
    const [liveTransform, setLiveTransform] = useState(transform);
    useEffect(() => { setLiveTransform(transform); }, [transform]);

    const [debouncedSetTransformInHistory] = useDebouncedCallback(setTransformInHistory, 100);
    
    const [selection, setSelection] = useState<SelectionRect | null>(null);
    const [drawingSelection, setDrawingSelection] = useState<SelectionRect | null>(null);
    const [ocrSelection, setOcrSelection] = useState<SelectionRect | null>(null);


    const [isPanning, setIsPanning] = useState(false);
    const [isSelecting, setIsSelecting] = useState(false);
    const [startPoint, setStartPoint] = useState<Point>({ x: 0, y: 0 });

    const [ocrText, setOcrText] = useState('');
    const [isOcrLoading, setIsOcrLoading] = useState(false);
    const [isParsing, setIsParsing] = useState(false);
    const [statusMessage, setStatusMessage] = useState('Welcome to Elysian Scribe v3.0');
    const [streetViewModalUrl, setStreetViewModalUrl] = useState<string | null>(null);

    const [isGeneratingImage, setIsGeneratingImage] = useState(false);
    const [generatedImage, setGeneratedImage] = useState<string | null>(null);


    // Refs
    const imageRef = useRef<HTMLImageElement>(null);
    const headstoneFileInputRef = useRef<HTMLInputElement>(null);
    const localConnector = useMemo(() => new LocalServiceConnector(), []);

    // --- Logic & Handlers (Callbacks are memoized) ---

    const updateStatus = useCallback((msg: string, duration: number = 5000) => {
        setStatusMessage(msg);
        setTimeout(() => setStatusMessage(''), duration);
    }, []);

    const handleSaveSettings = useCallback((settings: AiSettings) => {
        setAiSettings(settings);
        localStorage.setItem('aiSettings', JSON.stringify(settings));
        setIsSettingsModalOpen(false);
        updateStatus(`AI settings saved.`);
    }, [updateStatus]);

    const handleLoadHeadstones = useCallback((e: ChangeEvent<HTMLInputElement>) => {
        const newFiles = fileListToImageFile(e.target.files);
        setHeadstoneFiles(newFiles);
        if (newFiles.length > 0) {
            setCurrentImageIndex(0);
        } else {
            setCurrentImageIndex(-1);
        }
        setBatchResults([]); // Clear previous batch results
        setIsReviewPanelVisible(false); // Hide review panel
        updateStatus(`Loaded ${newFiles.length} headstone images.`);
    }, [updateStatus]);

    const saveCurrentRecord = useCallback(() => {
        // Use the ref to get the latest record without adding it as a dependency.
        if (currentRecordRef.current) {
            setRecords(prev => new Map(prev).set(currentRecordRef.current!.imageFilename, currentRecordRef.current!));
        }
    }, []);

    const [debouncedSaveRecord] = useDebouncedCallback(saveCurrentRecord, 500);

    const navigateImage = useCallback((direction: number) => {
        saveCurrentRecord();
        const newIndex = currentImageIndex + direction;
        if (newIndex >= 0 && newIndex < headstoneFiles.length) {
            setCurrentImageIndex(newIndex);
        }
    }, [saveCurrentRecord, currentImageIndex, headstoneFiles.length]);

    const selectImage = useCallback((index: number) => {
        saveCurrentRecord();
        setCurrentImageIndex(index);
    }, [saveCurrentRecord]);

     const selectImageByFilename = useCallback((filename: string) => {
        const index = headstoneFiles.findIndex(f => f.file.name === filename);
        if (index !== -1) {
            selectImage(index);
            setIsReviewPanelVisible(true); // Keep review panel open for easy navigation
        }
    }, [headstoneFiles, selectImage]);

    useEffect(() => {
        if (currentImageIndex === -1 || !headstoneFiles[currentImageIndex]) {
            resetRecordHistory(null);
            return;
        }
        const filename = headstoneFiles[currentImageIndex].file.name;
        const recordToLoad = records.get(filename)
            ? records.get(filename)!
            : {
                imageFilename: filename,
                plotLocation: '',
                gpsCoordinates: { latitude: '', longitude: '' },
                epitaph: '',
                people: [{ id: crypto.randomUUID(), firstName: '', middleName: '', lastName: '', born: '', died: '' }],
                ocrOptions: { ...DEFAULT_OCR_OPTIONS }
            };

        resetRecordHistory(recordToLoad);
        resetTransformHistory(INITIAL_TRANSFORM);
        setSelection(null);
        setDrawingSelection(null);
        setOcrText('');
        setOcrSelection(null);
    }, [currentImageIndex, headstoneFiles, records, resetRecordHistory, resetTransformHistory]);

    const handleWheel = useCallback((e: React.WheelEvent<HTMLDivElement>) => {
        e.preventDefault();

        let minZoom = 0.1; // Default minimum zoom if image isn't loaded
        if (imageRef.current) {
            const { naturalWidth, naturalHeight } = imageRef.current;
            const { width: cWidth, height: cHeight } = e.currentTarget.getBoundingClientRect();

            if (naturalWidth > 0 && naturalHeight > 0) { // Avoid division by zero
                const scaleX = cWidth / naturalWidth;
                const scaleY = cHeight / naturalHeight;
                minZoom = Math.min(scaleX, scaleY);
            }
        }

        const scaleAmount = 1.1;
        setLiveTransform(prev => {
            const newZoom = e.deltaY > 0 ? prev.zoom / scaleAmount : prev.zoom * scaleAmount;
            // Use the dynamically calculated minZoom as the lower bound
            const clampedZoom = Math.max(minZoom, Math.min(newZoom, 10));
            const newLiveTransform = { ...prev, zoom: clampedZoom };
            debouncedSetTransformInHistory(newLiveTransform);
            return newLiveTransform;
        });
    }, [debouncedSetTransformInHistory]);

    const handleZoomSliderChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
        const newZoom = parseFloat(e.target.value);
        const clampedZoom = Math.max(0.1, Math.min(newZoom, 10)); // Safety clamp matches wheel zoom
        const newTransform = { ...liveTransform, zoom: clampedZoom };
        setLiveTransform(newTransform);
        debouncedSetTransformInHistory(newTransform);
    }, [liveTransform, debouncedSetTransformInHistory]);

    const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
        e.preventDefault();
        const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
        const point = { x: e.clientX - rect.left, y: e.clientY - rect.top };
        setStartPoint(point);

        if (e.button === 2) { // Right click
            setIsPanning(true);
        } else if (e.button === 0) { // Left click
            setIsSelecting(true);
            setSelection(null); 
            setOcrSelection(null);
            setDrawingSelection({ x: point.x, y: point.y, width: 0, height: 0 });
        }
    }, []);

    const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
        if (isPanning) {
            if (!imageRef.current) return;
            
            const { naturalWidth, naturalHeight } = imageRef.current;
            const { width: containerWidth, height: containerHeight } = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
            const { zoom } = liveTransform;

            setLiveTransform(prev => {
                const newPanX = prev.pan.x + e.movementX;
                const newPanY = prev.pan.y + e.movementY;
                
                const scaledW = naturalWidth * zoom;
                const scaledH = naturalHeight * zoom;

                // Calculate horizontal bounds
                const boundX = (scaledW - containerWidth) / 2;
                const clampedX = scaledW > containerWidth 
                    ? Math.max(-boundX, Math.min(boundX, newPanX))
                    : 0; // Center if image is smaller than container

                // Calculate vertical bounds
                const boundY = (scaledH - containerHeight) / 2;
                const clampedY = scaledH > containerHeight
                    ? Math.max(-boundY, Math.min(boundY, newPanY))
                    : 0; // Center if image is smaller than container

                return { ...prev, pan: { x: clampedX, y: clampedY }};
            });
        }
        if (isSelecting) {
            const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
            const currentX = e.clientX - rect.left;
            const currentY = e.clientY - rect.top;
            
            setDrawingSelection({
                x: Math.min(startPoint.x, currentX),
                y: Math.min(startPoint.y, currentY),
                width: Math.abs(currentX - startPoint.x),
                height: Math.abs(currentY - startPoint.y),
            });
        }
    }, [isPanning, isSelecting, startPoint.x, startPoint.y, liveTransform.zoom]);

    const handleMouseUp = useCallback(() => {
        if (isPanning) {
            setTransformInHistory(liveTransform);
        }
        if (isSelecting && drawingSelection && drawingSelection.width > 5 && drawingSelection.height > 5 && imageRef.current && imageRef.current.parentElement) {
            const containerRect = imageRef.current.parentElement.parentElement!.getBoundingClientRect();
            const imageSize = { width: imageRef.current.naturalWidth, height: imageRef.current.naturalHeight };

            const topLeftScreen = { x: drawingSelection.x, y: drawingSelection.y };
            const bottomRightScreen = { x: drawingSelection.x + drawingSelection.width, y: drawingSelection.y + drawingSelection.height };
            
            const topLeftImage = screenToImagePoint(topLeftScreen, liveTransform, containerRect, imageSize);
            const bottomRightImage = screenToImagePoint(bottomRightScreen, liveTransform, containerRect, imageSize);

            setSelection({
                x: Math.min(topLeftImage.x, bottomRightImage.x),
                y: Math.min(topLeftImage.y, bottomRightImage.y),
                width: Math.abs(bottomRightImage.x - topLeftImage.x),
                height: Math.abs(bottomRightImage.y - topLeftImage.y),
            });
        }
        
        setIsPanning(false);
        setIsSelecting(false);
        setDrawingSelection(null);
    }, [isPanning, isSelecting, drawingSelection, liveTransform, setTransformInHistory]);

    const fitToScreen = useCallback(() => {
        if (!imageRef.current || !imageRef.current.parentElement) return;
        const { naturalWidth, naturalHeight } = imageRef.current;
        const { width: cWidth, height: cHeight } = imageRef.current.parentElement.parentElement!.getBoundingClientRect();
        const scaleX = cWidth / naturalWidth;
        const scaleY = cHeight / naturalHeight;
        setTransformInHistory({ ...INITIAL_TRANSFORM, zoom: Math.min(scaleX, scaleY) });
        setSelection(null);
        setOcrSelection(null);
        setDrawingSelection(null);
    }, [setTransformInHistory]);
    
    const handleRunOCR = useCallback(async () => {
        if (!selection || !imageRef.current || !currentRecordRef.current) {
            updateStatus("Please make a selection on the image first.");
            return;
        }
        setOcrSelection(selection);
        setIsOcrLoading(true);
        setOcrText("Running OCR...");
        try {
            const { base64, mimeType } = await getCroppedBase64(imageRef.current, selection);
            const text = await extractTextFromImage(base64, mimeType, currentRecordRef.current.ocrOptions, aiSettings.ocr, aiSettings.localOcr);
            setOcrText(text);
            updateStatus("OCR completed successfully.");
        } catch (error: any) {
            console.error("OCR failed:", error);
            const errorMessage = `OCR Failed: ${error.message}`;
            setOcrText(errorMessage);
            updateStatus(errorMessage, 8000);
        } finally {
            setIsOcrLoading(false);
        }
    }, [selection, updateStatus, aiSettings.ocr, aiSettings.localOcr]);

    const handleAutoParse = useCallback(async () => {
        if (!ocrText || !currentRecordRef.current || ocrText.startsWith("OCR Failed:")) {
            updateStatus("Cannot auto-parse: No valid OCR text available.", 4000);
            return;
        }

        setIsParsing(true);
        updateStatus(`Analyzing text with ${aiSettings.parsing === 'google-ai' ? 'Google AI' : 'LM Studio'}...`);

        try {
            let parsedData: { epitaph: string; people: Omit<Person, 'id'>[] };

            if (aiSettings.parsing === 'google-ai') {
                parsedData = await parseOcrTextToRecord(ocrText);
            } else {
                if (!currentRecordRef.current) throw new Error("Current record is not available.");
                parsedData = await parseWithLmStudio(ocrText, currentRecordRef.current.ocrOptions);
            }
            
            const validPeople = parsedData.people.filter(p => p.firstName?.trim() || p.lastName?.trim() || p.died?.trim());

            if (validPeople.length === 0) {
                updateStatus("AI could not find individuals. Epitaph updated.", 5000);
                setCurrentRecord(prev => prev ? { ...prev, epitaph: parsedData.epitaph || prev.epitaph } : null);
            } else {
                const newPeople: Person[] = validPeople.map(p => ({
                    ...p,
                    id: crypto.randomUUID(),
                    firstName: capitalizeName(p.firstName),
                    middleName: capitalizeName(p.middleName),
                    lastName: capitalizeName(p.lastName),
                }));
                
                setCurrentRecord(prev => {
                    if (!prev) return null;
                    return {
                        ...prev,
                        epitaph: parsedData.epitaph || prev.epitaph,
                        people: newPeople,
                    };
                });
                updateStatus(`Form auto-filled with ${newPeople.length} individual(s). Please review.`, 5000);
            }

        } catch (error: any) {
            console.error("Auto-parse failed:", error);
            const errorMessage = `Auto-parse Failed: ${error.message}`;
            updateStatus(errorMessage, 8000);
        } finally {
            setIsParsing(false);
        }
    }, [ocrText, aiSettings.parsing, setCurrentRecord, updateStatus]);

    const handleCropAndOverwrite = useCallback(async () => {
        const currentImage = headstoneFiles[currentImageIndex];
        if (!currentImage || !selection) {
            updateStatus("Cannot crop: No image or selection available.", 5000);
            return;
        }

        updateStatus("Cropping image...");
        const originalFile = currentImage.file;

        try {
            const imageBitmap = await createImageBitmap(originalFile);
            const canvas = document.createElement('canvas');
            canvas.width = selection.width;
            canvas.height = selection.height;
            const ctx = canvas.getContext('2d');
            if (!ctx) throw new Error("Could not get canvas context for cropping.");

            ctx.drawImage(
                imageBitmap,
                selection.x, selection.y, selection.width, selection.height,
                0, 0, selection.width, selection.height
            );

            const blob: Blob | null = await new Promise(resolve => canvas.toBlob(resolve, originalFile.type, 0.95));
            if (!blob) throw new Error("Failed to create blob from cropped image.");

            const newCroppedFile = new File([blob], originalFile.name, { type: originalFile.type });
            const newImageFile: ImageFile = { file: newCroppedFile, url: URL.createObjectURL(newCroppedFile) };
            URL.revokeObjectURL(currentImage.url);

            setHeadstoneFiles(prevFiles => {
                const newFiles = [...prevFiles];
                newFiles[currentImageIndex] = newImageFile;
                return newFiles;
            });
            
            updateStatus(`Image "${originalFile.name}" cropped and overwritten.`);
        } catch(error) {
            console.error("Cropping failed:", error);
            updateStatus("An error occurred during the crop operation.", 8000);
        }
    }, [headstoneFiles, currentImageIndex, selection, updateStatus]);


    const exportToCSV = useCallback(() => {
        saveCurrentRecord();
        let csvContent = "image_filename,plot_location,gps_latitude,gps_longitude,epitaph,person_first_name,person_middle_name,person_last_name,born,died\n";
        
        records.forEach((record) => {
            record.people.forEach(person => {
                const row = [
                    record.imageFilename,
                    `"${record.plotLocation.replace(/"/g, '""')}"`,
                    record.gpsCoordinates?.latitude || '',
                    record.gpsCoordinates?.longitude || '',
                    `"${record.epitaph.replace(/"/g, '""')}"`,
                    `"${person.firstName.replace(/"/g, '""')}"`,
                    `"${person.middleName.replace(/"/g, '""')}"`,
                    `"${person.lastName.replace(/"/g, '""')}"`,
                    person.born,
                    person.died
                ].join(',');
                csvContent += row + "\n";
            });
        });

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        if (link.download !== undefined) {
            const url = URL.createObjectURL(blob);
            link.setAttribute("href", url);
            link.setAttribute("download", "database_final.csv");
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
        updateStatus("Database exported to database_final.csv");
    }, [records, saveCurrentRecord, updateStatus]);
    
    const handleMapInteraction = useCallback((coords: { lat: number; lng: number }) => {
        if (!currentRecordRef.current) return;
        
        const newRecord = {
            ...currentRecordRef.current,
            gpsCoordinates: {
                latitude: coords.lat.toFixed(6),
                longitude: coords.lng.toFixed(6),
            }
        };
        // Use the immediate setter from the history hook for this interaction
        setCurrentRecord(newRecord);
        debouncedSaveRecord();
        updateStatus("GPS coordinates updated from map.", 3000);
    }, [setCurrentRecord, debouncedSaveRecord, updateStatus]);
    
    const handleGetGpsFromImage = useCallback(async () => {
        const imageFile = headstoneFiles[currentImageIndex];
        if (!imageFile) {
            updateStatus("No image selected to get GPS data from.", 4000);
            return;
        }
    
        updateStatus("Reading GPS data from image...", 3000);
    
        try {
            const coords = await getGpsFromExif(imageFile.file);
    
            if (coords) {
                // Update the record directly for immediate feedback
                setCurrentRecord(prev => {
                    if (!prev) return null;
                    const newRecord = {
                        ...prev,
                        gpsCoordinates: {
                            latitude: coords.latitude.toFixed(6),
                            longitude: coords.longitude.toFixed(6)
                        }
                    };
                    return newRecord;
                });
                debouncedSaveRecord();
                updateStatus("GPS coordinates extracted from image.", 5000);
            } else {
                updateStatus("No GPS data found in the image file.", 5000);
            }
        } catch (error) {
            console.error("Error reading EXIF data:", error);
            updateStatus("Failed to read GPS data from image.", 5000);
        }
    }, [currentImageIndex, headstoneFiles, updateStatus, setCurrentRecord, debouncedSaveRecord]);

    const handleUploadStreetViewPhoto = useCallback((file: File) => {
        if (!currentRecordRef.current) return;

        const newUrl = URL.createObjectURL(file);
        const newPhotoFile: ImageFile = { file, url: newUrl };

        setStreetViewPhotos(prevMap => {
            const newMap = new Map(prevMap);
            // Clean up old URL if replacing
            const oldFilename = currentRecordRef.current?.streetViewPhotoFilename;
            if (oldFilename && oldFilename !== file.name) {
                const oldFile = newMap.get(oldFilename);
                if (oldFile) URL.revokeObjectURL(oldFile.url);
            }
            newMap.set(file.name, newPhotoFile);
            return newMap;
        });

        setCurrentRecord(prev => prev ? { ...prev, streetViewPhotoFilename: file.name } : null);
        debouncedSaveRecord();
        updateStatus(`Uploaded 360° photo: ${file.name}`, 4000);
    }, [setCurrentRecord, debouncedSaveRecord, updateStatus]);

    const handleRemoveStreetViewPhoto = useCallback(() => {
        if (!currentRecordRef.current?.streetViewPhotoFilename) return;

        const filenameToRemove = currentRecordRef.current.streetViewPhotoFilename;
        setStreetViewPhotos(prevMap => {
            const newMap = new Map(prevMap);
            const fileToRemove = newMap.get(filenameToRemove);
            if (fileToRemove) {
                URL.revokeObjectURL(fileToRemove.url);
                newMap.delete(filenameToRemove);
            }
            return newMap;
        });

        setCurrentRecord(prev => prev ? { ...prev, streetViewPhotoFilename: undefined } : null);
        debouncedSaveRecord();
        updateStatus(`Removed 360° photo.`, 4000);
    }, [setCurrentRecord, debouncedSaveRecord, updateStatus]);

    const handleStreetViewRequest = useCallback(() => {
        const record = currentRecordRef.current;
        if (!record) return;

        if (record.streetViewPhotoFilename) {
            const photo = streetViewPhotos.get(record.streetViewPhotoFilename);
            if (photo) {
                setStreetViewModalUrl(photo.url);
            } else {
                updateStatus("Custom 360° photo data not found.", 5000);
            }
        } else {
            const lat = parseFloat(record.gpsCoordinates.latitude);
            const lng = parseFloat(record.gpsCoordinates.longitude);
            if (!isNaN(lat) && !isNaN(lng)) {
                const url = `https://www.google.com/maps?q&layer=c&cbll=${lat},${lng}&cbp=12,0,0,0,0`;
                window.open(url, '_blank', 'noopener,noreferrer');
                updateStatus("Opening Google Street View in a new tab.", 3000);
            } else {
                updateStatus("No valid GPS coordinates for Street View.", 4000);
            }
        }
    }, [streetViewPhotos, updateStatus]);

    const handleAutonomousBatch = useCallback(async () => {
        if (headstoneFiles.length === 0) {
            updateStatus("No images loaded to process.", 4000);
            return;
        }

        saveCurrentRecord();
        setIsMapPanelVisible(false);
        setIsReviewPanelVisible(false);
        setIsBatchRunning(true);
        cancelBatchRef.current = false;
        setBatchResults([]);
        
        const newRecords = new Map(records);
        const results: BatchProcessResult[] = [];

        for (let i = 0; i < headstoneFiles.length; i++) {
            if (cancelBatchRef.current) break;

            const imageFile = headstoneFiles[i];
            const filename = imageFile.file.name;
            const mimeType = imageFile.file.type || 'image/jpeg';
            let status: BatchProcessResult['status'] = 'success';
            let errorMessage: string | undefined;

            // Step 1: Initialize Record and get GPS
            setBatchProgress({ current: i + 1, total: headstoneFiles.length, step: 'Extracting GPS...', filename });
            let record: CemeteryRecord = records.get(filename) || {
                imageFilename: filename,
                plotLocation: '',
                gpsCoordinates: { latitude: '', longitude: '' },
                epitaph: '',
                people: [{ id: crypto.randomUUID(), firstName: '', middleName: '', lastName: '', born: '', died: '' }],
                ocrOptions: { ...DEFAULT_OCR_OPTIONS }
            };

            try {
                const coords = await getGpsFromExif(imageFile.file);
                if (coords) {
                    record.gpsCoordinates = {
                        latitude: coords.latitude.toFixed(6),
                        longitude: coords.longitude.toFixed(6)
                    };
                }
            } catch (e) {
                console.warn(`GPS extraction failed for ${filename}:`, e);
            }
            
            const image = new Image();
            image.src = imageFile.url;
            await new Promise(resolve => { image.onload = resolve });

            // Step 2 & 3: Analyze Image with AI, respecting provider choice
            try {
                const base64 = await getFullImageBase64(image, mimeType);
                let parsedData: { epitaph: string; people: Omit<Person, 'id'>[] };

                if (aiSettings.parsing === 'google-ai') {
                    setBatchProgress({ current: i + 1, total: headstoneFiles.length, step: 'Analyzing with Google AI...', filename });
                    parsedData = await extractAndParseImage(base64, mimeType, record.ocrOptions);
                } else {
                    // Step 2a: OCR (Cloud or Local)
                    const ocrStepMessage = aiSettings.ocr === 'local-ocr' ? 'Running Local OCR...' : 'Running OCR...';
                    setBatchProgress({ current: i + 1, total: headstoneFiles.length, step: ocrStepMessage, filename });
                    const textFromOcr = await extractTextFromImage(base64, mimeType, record.ocrOptions, aiSettings.ocr, aiSettings.localOcr);
                    if (textFromOcr.startsWith('OCR Failed:')) throw new Error(textFromOcr);

                    // Step 2b: Parsing (Local)
                    setBatchProgress({ current: i + 1, total: headstoneFiles.length, step: 'Parsing with Local AI...', filename });
                    parsedData = await parseWithLmStudio(textFromOcr, record.ocrOptions);
                }

                const validPeople = parsedData.people.filter(p => p.firstName?.trim() || p.lastName?.trim());

                if (validPeople.length === 0) {
                    status = 'partial';
                    record.epitaph = parsedData.epitaph;
                    record.people = [{ id: crypto.randomUUID(), firstName: '', middleName: '', lastName: '', born: '', died: '' }];
                } else {
                    record.epitaph = parsedData.epitaph;
                    record.people = validPeople.map(p => ({
                        ...p,
                        id: crypto.randomUUID(),
                        firstName: capitalizeName(p.firstName),
                        middleName: capitalizeName(p.middleName),
                        lastName: capitalizeName(p.lastName),
                    }));
                }
            } catch (e: any) {
                console.error(`AI analysis failed for ${filename}:`, e);
                status = 'error';
                const step = aiSettings.parsing === 'google-ai' ? 'AI Analysis' : (e.message.includes('OCR Failed:') ? 'OCR' : 'Local AI Parsing');
                errorMessage = `${step} Failed: ${e.message}`;
            }

            results.push({ status, imageFilename: filename, record, errorMessage });
            newRecords.set(filename, record);
            setBatchResults([...results]);

            // Add a delay between API calls to avoid hitting rate limits.
            if (i < headstoneFiles.length - 1) {
                await new Promise(resolve => setTimeout(resolve, 10100));
            }
        }
        
        setRecords(newRecords);
        setIsBatchRunning(false);
        setBatchProgress(null);
        updateStatus(`Autonomous batch completed${cancelBatchRef.current ? ' (Cancelled)' : ''}.`, 5000);
        setIsReviewPanelVisible(true);
        setIsMapPanelVisible(false);

    }, [headstoneFiles, records, saveCurrentRecord, updateStatus, aiSettings]);

    const handleGenerateImage = useCallback(async (prompt: string) => {
        if (!prompt.trim()) {
            updateStatus("Please enter a prompt for image generation.", 4000);
            return;
        }
        setIsGeneratingImage(true);
        setGeneratedImage(null);
        updateStatus("Generating concept art with local AI...");

        try {
            const response = await localConnector.generateImage(prompt);
            if (response.images && response.images.length > 0) {
                const base64Image = response.images[0];
                setGeneratedImage(`data:image/png;base64,${base64Image}`);
                updateStatus("Image generation successful.", 5000);
            } else {
                throw new Error("Local service returned no images.");
            }
        } catch (error: any) {
            console.error("Image generation failed:", error);
            updateStatus(`Image Generation Failed: ${error.message}`, 8000);
        } finally {
            setIsGeneratingImage(false);
        }
    }, [localConnector, updateStatus]);


    const currentImage = headstoneFiles[currentImageIndex];

    return (
        <div className="flex h-screen w-screen bg-gray-900 text-gray-200 font-sans">
            <input type="file" multiple webkitdirectory="" ref={headstoneFileInputRef} onChange={handleLoadHeadstones} className="hidden" />
            
            <MapPanel
                isVisible={isMapPanelVisible}
                records={records}
                currentRecord={currentRecord}
                onMapInteraction={handleMapInteraction}
                onMarkerClick={selectImageByFilename}
                onUpdateStatus={updateStatus}
                onStreetViewClick={handleStreetViewRequest}
                hasCustomStreetView={!!currentRecord?.streetViewPhotoFilename}
            />

            <ReviewPanel 
                isVisible={isReviewPanelVisible}
                results={batchResults}
                onSelect={selectImageByFilename}
                onClose={() => setIsReviewPanelVisible(false)}
            />

            <main className="flex-1 flex flex-col p-4 gap-4 overflow-hidden">
                <div className="flex-1 grid grid-cols-12 gap-4 overflow-hidden">
                    <div className="col-span-12 md:col-span-8 flex flex-col gap-4 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-800 pr-2">
                        <div className="flex-shrink-0 flex gap-2 items-center flex-wrap">
                             <Button onClick={() => { setIsMapPanelVisible(prev => !prev); setIsReviewPanelVisible(false); }} variant="secondary" title={isMapPanelVisible ? 'Hide Map Panel' : 'Show Map Panel'}>{isMapPanelVisible ? 'Hide Map' : 'Show Map'}</Button>
                            <Button onClick={() => { setIsReviewPanelVisible(prev => !prev); setIsMapPanelVisible(false); }} variant="secondary" disabled={batchResults.length === 0} title={isReviewPanelVisible ? 'Hide Review Panel' : 'Show Review Panel'}>
                                {isReviewPanelVisible ? 'Hide Review' : 'Show Review'}
                            </Button>
                            <Button onClick={() => headstoneFileInputRef.current?.click()}>Load Headstones Folder</Button>
                             <Button onClick={handleAutonomousBatch} disabled={isBatchRunning || headstoneFiles.length === 0} variant="primary">Autonomous Batch</Button>
                            <div className="flex-grow text-center">
                                <h1 className="text-2xl font-bold text-indigo-400 hidden sm:inline-block">Elysian Scribe v3.0</h1>
                            </div>
                            <Button onClick={() => setIsSettingsModalOpen(true)} variant="secondary" className="p-2" title="Configure AI Settings">
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                  <path fillRule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
                                </svg>
                            </Button>
                        </div>
                        <Panel className="flex-1 flex flex-col overflow-hidden">
                            <ImageWorkstation 
                                currentImage={currentImage}
                                liveTransform={liveTransform}
                                ocrSelection={ocrSelection}
                                selection={selection}
                                drawingSelection={drawingSelection}
                                onWheel={handleWheel}
                                onMouseDown={handleMouseDown}
                                onMouseMove={handleMouseMove}
                                onMouseUp={handleMouseUp}
                                onMouseLeave={handleMouseUp}
                                onContextMenu={e => e.preventDefault()}
                                onImageRef={imageRef}
                            />
                        </Panel>
                        <Panel className="flex-shrink-0">
                           <div className="h-24 overflow-x-auto overflow-y-hidden whitespace-nowrap scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-800">
                                {headstoneFiles.map((img, index) => (
                                    <img key={img.url} src={img.url} onClick={() => selectImage(index)} alt={img.file.name} className={`inline-block h-full w-auto mr-2 rounded-md cursor-pointer border-2 ${index === currentImageIndex ? 'border-indigo-500' : 'border-transparent hover:border-gray-500'}`} />
                                ))}
                            </div>
                        </Panel>
                        <Panel className="flex-shrink-0 flex items-center gap-4 flex-wrap">
                            <span className="font-semibold">Rotate:</span>
                            <Button onClick={() => setTransformInHistory(t => ({ ...t, rotation: t.rotation - 90 }))} variant="secondary">Left</Button>
                            <Button onClick={() => setTransformInHistory(t => ({ ...t, rotation: t.rotation + 90 }))} variant="secondary">Right</Button>
                            <input type="range" min="-10" max="10" step="0.1" value={transform.rotation % 90} onChange={(e) => setTransformInHistory(t => ({...t, rotation: Math.floor(t.rotation / 90) * 90 + parseFloat(e.target.value)}))} className="w-32"/>
                            <Button onClick={undoTransform} disabled={!canUndoTransform} variant="secondary">Undo</Button>
                            <Button onClick={redoTransform} disabled={!canRedoTransform} variant="secondary">Redo</Button>
                            
                            <div className="border-l border-gray-600 h-6 mx-2"></div>
                            <span className="font-semibold">Zoom:</span>
                            <input
                              type="range"
                              min="0.1"
                              max="10"
                              step="0.1"
                              value={liveTransform.zoom}
                              onChange={handleZoomSliderChange}
                              className="w-32 cursor-pointer"
                              aria-label="Image zoom"
                            />
                            <span className="w-16 text-center tabular-nums">{Math.round(liveTransform.zoom * 100)}%</span>

                            <div className="flex-grow" />
                            <Button onClick={handleCropAndOverwrite} variant="warning" disabled={!selection}>Crop & Overwrite</Button>
                            <Button onClick={() => resetTransformHistory(INITIAL_TRANSFORM)} variant="secondary">Revert</Button>
                            <Button onClick={fitToScreen} variant="secondary">Fit to Screen</Button>
                        </Panel>
                         <ImageGenerationPanel
                            currentRecord={currentRecord}
                            isGenerating={isGeneratingImage}
                            generatedImage={generatedImage}
                            onGenerate={handleGenerateImage}
                        />
                    </div>
                    
                    <DataEntryPanel 
                        record={currentRecord}
                        onCommitChange={(newRecord) => {
                            setCurrentRecord(newRecord);
                            debouncedSaveRecord();
                        }}
                        ocrText={ocrText}
                        isOcrLoading={isOcrLoading}
                        selection={selection}
                        onRunOCR={handleRunOCR}
                        onAutoParse={handleAutoParse}
                        isParsing={isParsing}
                        onNavigateImage={navigateImage}
                        currentImageIndex={currentImageIndex}
                        headstoneFileCount={headstoneFiles.length}
                        onUndo={undoRecord}
                        canUndo={canUndoRecord}
                        onRedo={redoRecord}
                        canRedo={canRedoRecord}
                        onSave={saveCurrentRecord}
                        onExport={exportToCSV}
                        onUpdateStatus={updateStatus}
                        onUploadStreetViewPhoto={handleUploadStreetViewPhoto}
                        onRemoveStreetViewPhoto={handleRemoveStreetViewPhoto}
                        onGetGpsFromImage={handleGetGpsFromImage}
                    />
                </div>
                
                <footer className="flex-shrink-0 bg-gray-700 rounded-lg shadow-md px-4 py-1 text-sm text-center">
                    {statusMessage}
                </footer>
            </main>

            <ProgressModal
                progress={batchProgress}
                onCancel={() => {
                    cancelBatchRef.current = true;
                    updateStatus("Cancelling batch process...", 3000);
                }}
            />

            <SettingsModal
                isOpen={isSettingsModalOpen}
                onClose={() => setIsSettingsModalOpen(false)}
                settings={aiSettings}
                onSave={handleSaveSettings}
            />

            {streetViewModalUrl && (
                <div 
                    className="fixed inset-0 bg-black bg-opacity-80 flex items-center justify-center z-50 cursor-pointer"
                    onClick={() => setStreetViewModalUrl(null)}
                >
                    <div className="relative" onClick={e => e.stopPropagation()}>
                        <img src={streetViewModalUrl} alt="360 degree panoramic view" className="max-w-[95vw] max-h-[95vh] rounded-lg shadow-2xl" />
                        <button 
                            onClick={() => setStreetViewModalUrl(null)} 
                            className="absolute -top-3 -right-3 bg-gray-800 rounded-full p-2 text-white hover:bg-red-600 transition-colors focus:outline-none focus:ring-2 focus:ring-red-500"
                            aria-label="Close 360 photo viewer"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}