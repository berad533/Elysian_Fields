
import { GoogleGenAI, Type } from "@google/genai";
import type { OcrOptions, Person, AiOcrProvider, LocalOcrSettings } from '../types';
import { LocalServiceConnector } from './localServiceConnector';

if (!process.env.API_KEY) {
  console.error("API_KEY environment variable not set.");
}

const ai = new GoogleGenAI({ apiKey: process.env.API_KEY! });
const localConnector = new LocalServiceConnector();

const generatePrompt = (options: OcrOptions): string => {
    let basePrompt = "You are an expert genealogist specializing in reading headstones. Extract all text from this image of a headstone, preserving line breaks. The text might be weathered or difficult to read.";

    switch (options.mode) {
        case 'handwritten':
            basePrompt += " The inscription may be in a cursive or handwritten style. Pay close attention to faint, worn, or uneven lettering.";
            break;
        case 'damaged':
            basePrompt += " The stone is damaged, cracked, or heavily weathered. Try to reconstruct partial letters and words where possible, but only return text that is reasonably certain. Indicate unreadable characters with '[?]'.";
            break;
        case 'standard':
        default:
             basePrompt += " If no text is visible, return an empty string.";
            break;
    }

    if (options.language && options.language.trim() !== '') {
        basePrompt += ` The primary language on the stone is ${options.language}.`;
    }

    if (options.characterSet && options.characterSet.trim() !== '') {
        basePrompt += ` Only return characters found within this set: "${options.characterSet}". Ignore all other characters.`;
    }

    if (options.customPrompt && options.customPrompt.trim() !== '') {
        basePrompt += ` Additional user instructions that you must follow: "${options.customPrompt}".`;
    }

    if (options.negativePrompt && options.negativePrompt.trim() !== '') {
        basePrompt += ` You must strictly ignore and not extract the following: "${options.negativePrompt}".`;
    }

    return basePrompt;
};

/**
 * Extracts text from a given image using the Gemini API.
 * @param base64Image A base64 encoded image string (without the 'data:image/jpeg;base64,' prefix).
 * @param mimeType The MIME type of the image (e.g., 'image/jpeg').
 * @param options Advanced OCR processing options.
 * @returns The extracted text as a string.
 * @throws An error with a user-friendly message if the API call fails.
 */
async function extractTextWithGoogleAI(base64Image: string, mimeType: string, options: OcrOptions): Promise<string> {
  try {
    const prompt = generatePrompt(options);

    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: {
        parts: [
          {
            inlineData: {
              data: base64Image,
              mimeType,
            },
          },
          {
            text: prompt,
          },
        ],
      },
    });

    return response.text;
  } catch (error: any) {
    console.error("Error calling Gemini API:", error);

    let errorMessage = "An unknown error occurred during OCR processing.";

    if (error && typeof error.message === 'string') {
        const msg = error.message.toLowerCase();
        if (msg.includes('api key not valid')) {
            errorMessage = "Invalid API Key. Please check your configuration.";
        } else if (msg.includes('quota')) {
            errorMessage = "API quota exceeded. Please check your usage or billing.";
        } else if (msg.includes('candidate was blocked due to safety')) {
            errorMessage = "The image was blocked by safety filters. Try a different image or selection.";
        } else if (msg.includes('failed to fetch') || msg.includes('network request failed')) {
            errorMessage = "Network issue. Could not connect to the Gemini API.";
        } else {
            // Use the first line of the original error for context if it's not a known case.
            errorMessage = error.message.split('\n')[0];
        }
    }
    
    throw new Error(errorMessage);
  }
}

/**
 * Extracts text from a given image using the configured AI provider.
 * This function acts as a router to different OCR services.
 * @param base64Image A base64 encoded image string.
 * @param mimeType The MIME type of the image.
 * @param options Advanced OCR processing options.
 * @param provider The AI provider to use for OCR ('google-ai' or 'local-ocr').
 * @param localOcrSettings Configuration for the local OCR service.
 * @returns The extracted text as a string.
 * @throws An error with a user-friendly message if the API call fails.
 */
export async function extractTextFromImage(
    base64Image: string,
    mimeType: string,
    options: OcrOptions,
    provider: AiOcrProvider,
    localOcrSettings: LocalOcrSettings
): Promise<string> {
  if (provider === 'local-ocr') {
    try {
      const result = await localConnector.performOcr(base64Image, mimeType, localOcrSettings);
      return result.text;
    } catch (error: any) {
      // The connector already formats the error message nicely.
      console.error("Error calling local OCR service:", error);
      throw error; 
    }
  }
  // Default to Google AI
  return extractTextWithGoogleAI(base64Image, mimeType, options);
}


/**
 * Parses a block of text from a headstone into structured data using Google AI.
 * @param ocrText The raw text extracted from an OCR process.
 * @returns A structured object containing the epitaph and a list of people.
 * @throws An error with a user-friendly message if the API call or parsing fails.
 */
export async function parseOcrTextToRecord(ocrText: string): Promise<{ epitaph: string; people: Omit<Person, 'id'>[] }> {
    try {
        const prompt = `You are a helpful genealogical assistant. Analyze the following text extracted from a headstone and structure it into a JSON object. Identify all individuals, their names (first, middle, last), their birth and death dates, and any epitaph.

Headstone Text:
---
${ocrText}
---

Provide the output in the specified JSON format. If a piece of information (like a middle name) is not present, use an empty string. The 'people' array should contain an object for each person found.`;

        const response = await ai.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: prompt,
            config: {
                responseMimeType: "application/json",
                responseSchema: {
                    type: Type.OBJECT,
                    properties: {
                        epitaph: {
                            type: Type.STRING,
                            description: "Any epitaph, verse, or phrases like 'In loving memory of' found on the headstone. Exclude names and dates from the epitaph."
                        },
                        people: {
                            type: Type.ARRAY,
                            description: "An array of all individuals identified on the headstone.",
                            items: {
                                type: Type.OBJECT,
                                properties: {
                                    firstName: { type: Type.STRING, description: "The person's first name." },
                                    middleName: { type: Type.STRING, description: "The person's middle name or initial. Use an empty string if not present." },
                                    lastName: { type: Type.STRING, description: "The person's last name." },
                                    born: { type: Type.STRING, description: "The full birth date (e.g., 'Jan 1, 1900'). Use an empty string if not present." },
                                    died: { type: Type.STRING, description: "The full death date (e.g., 'Dec 31, 1950'). Use an empty string if not present." }
                                }
                            }
                        }
                    }
                }
            }
        });
        
        const jsonString = response.text.trim().replace(/^```json\n?/, '').replace(/```$/, '');
        const parsed = JSON.parse(jsonString);

        if (!parsed || !Array.isArray(parsed.people)) {
            throw new Error("API returned an invalid data structure.");
        }

        return parsed;

    } catch (error: any) {
        console.error("Error parsing text with Gemini API:", error);
        let errorMessage = "An unknown error occurred during data parsing.";
        if (error && typeof error.message === 'string') {
             const msg = error.message.toLowerCase();
             if (msg.includes('api key not valid')) {
                 errorMessage = "Invalid API Key.";
             } else if (msg.includes('quota')) {
                 errorMessage = "API quota exceeded.";
             } else if (msg.includes('json')){
                 errorMessage = "Failed to parse the AI's response. The text may be ambiguous."
             } else {
                 errorMessage = error.message.split('\n')[0];
             }
        }
        throw new Error(errorMessage);
    }
}

/**
 * Parses a block of text from a headstone into structured data using a local LM Studio instance.
 * @param ocrText The raw text extracted from an OCR process.
 * @param options The OCR options, providing context about the text source.
 * @returns A structured object containing the epitaph and a list of people.
 * @throws An error with a user-friendly message if the API call or parsing fails.
 */
export async function parseWithLmStudio(ocrText: string, options: OcrOptions): Promise<{ epitaph: string; people: Omit<Person, 'id'>[] }> {
    const systemPrompt = `You are an expert genealogist and a helpful assistant that only responds with JSON.
Analyze the headstone text provided by the user and extract the information into a structured JSON object.

The JSON object must have the following structure:
{
  "epitaph": "string",
  "people": [
    {
      "firstName": "string",
      "middleName": "string",
      "lastName": "string",
      "born": "string",
      "died": "string"
    }
  ]
}

- If a piece of information (like a middle name or birth date) is not present, use an empty string "".
- The 'people' array should contain an object for each distinct person found.
- The 'epitaph' should contain any verse or phrases like "In loving memory of", but exclude names and dates.
- Do not include any explanation or introductory text in your response. Respond ONLY with the JSON object.`;

    let userPrompt = `Here is the headstone text:\n---\n${ocrText}\n---`;

    const contextParts: string[] = [];
    if (options.mode === 'damaged') {
        contextParts.push("The text was extracted from a damaged or weathered stone; be lenient with potential OCR errors.");
    } else if (options.mode === 'handwritten') {
        contextParts.push("The text was from a handwritten or faded inscription; be lenient with potential OCR errors.");
    }

    if (options.language) {
        contextParts.push(`The language of the inscription is likely ${options.language}.`);
    }
    
    if (options.customPrompt) {
        contextParts.push(`Pay special attention to this user instruction: "${options.customPrompt}".`);
    }

    if (contextParts.length > 0) {
        userPrompt += "\n\nImportant Context for Parsing:\n- " + contextParts.join("\n- ");
    }


    try {
        const content = await localConnector.getChatCompletion(
            [
                { role: "system", content: systemPrompt },
                { role: "user", content: userPrompt }
            ],
            { temperature: 0.2 }
        );
        
        // Make JSON parsing more robust by extracting content between the first '{' and last '}'
        const firstBrace = content.indexOf('{');
        const lastBrace = content.lastIndexOf('}');

        if (firstBrace === -1 || lastBrace === -1 || lastBrace < firstBrace) {
            throw new Error("Could not find a valid JSON object in the local AI's response.");
        }

        const jsonString = content.substring(firstBrace, lastBrace + 1);
        const parsed = JSON.parse(jsonString);

        if (!parsed || !Array.isArray(parsed.people)) {
            throw new Error("Local AI returned an invalid data structure.");
        }

        return parsed;

    } catch (error: any) {
        console.error("Error calling LM Studio via connector:", error);
        let errorMessage = "An unknown error occurred while contacting the local AI.";
        if (error && typeof error.message === 'string') {
             // The connector provides a good base message, we just add context for JSON parsing failures.
             if (error.message.includes('json') || error.message.includes('valid json object')) {
                 errorMessage = "Failed to parse the local AI's response. The model may not be following JSON format instructions."
             } else {
                 errorMessage = error.message;
             }
        }
        throw new Error(errorMessage);
    }
}


/**
 * Extracts and parses headstone data directly from an image in a single, efficient step.
 * @param base64Image A base64 encoded image string.
 * @param mimeType The MIME type of the image.
 * @param options Advanced OCR processing options.
 * @returns A structured object containing the epitaph and a list of people.
 * @throws An error with a user-friendly message if the API call or parsing fails.
 */
export async function extractAndParseImage(base64Image: string, mimeType: string, options: OcrOptions): Promise<{ epitaph: string; people: Omit<Person, 'id'>[] }> {
    try {
        const basePrompt = generatePrompt(options);
        const fullPrompt = `${basePrompt}\n\nAnalyze the image and structure all found information into the specified JSON format. Identify all individuals, their names (first, middle, last), their birth and death dates, and any epitaph. If a piece of information (like a middle name) is not present, use an empty string. The 'people' array should contain an object for each person found.`;

        const response = await ai.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: {
                parts: [
                    {
                        inlineData: {
                            data: base64Image,
                            mimeType,
                        },
                    },
                    {
                        text: fullPrompt,
                    },
                ],
            },
            config: {
                responseMimeType: "application/json",
                responseSchema: {
                    type: Type.OBJECT,
                    properties: {
                        epitaph: {
                            type: Type.STRING,
                            description: "Any epitaph, verse, or phrases like 'In loving memory of' found on the headstone. Exclude names and dates from the epitaph."
                        },
                        people: {
                            type: Type.ARRAY,
                            description: "An array of all individuals identified on the headstone.",
                            items: {
                                type: Type.OBJECT,
                                properties: {
                                    firstName: { type: Type.STRING, description: "The person's first name." },
                                    middleName: { type: Type.STRING, description: "The person's middle name or initial. Use an empty string if not present." },
                                    lastName: { type: Type.STRING, description: "The person's last name." },
                                    born: { type: Type.STRING, description: "The full birth date (e.g., 'Jan 1, 1900'). Use an empty string if not present." },
                                    died: { type: Type.STRING, description: "The full death date (e.g., 'Dec 31, 1950'). Use an empty string if not present." }
                                }
                            }
                        }
                    }
                }
            }
        });

        const jsonString = response.text.trim().replace(/^```json\n?/, '').replace(/```$/, '');
        const parsed = JSON.parse(jsonString);

        if (!parsed || !Array.isArray(parsed.people)) {
            throw new Error("API returned an invalid data structure.");
        }

        return parsed;

    } catch (error: any) {
        console.error("Error extracting and parsing image with Gemini API:", error);
        let errorMessage = "An unknown error occurred during AI analysis.";
        if (error && typeof error.message === 'string') {
             const msg = error.message.toLowerCase();
             if (msg.includes('api key not valid')) {
                 errorMessage = "Invalid API Key.";
             } else if (msg.includes('quota')) {
                 errorMessage = "API quota exceeded.";
             } else if (msg.includes('json')){
                 errorMessage = "Failed to parse the AI's response. The image may be ambiguous."
             } else if (msg.includes('candidate was blocked due to safety')) {
                errorMessage = "The image was blocked by safety filters.";
             } else {
                 errorMessage = error.message.split('\n')[0];
             }
        }
        throw new Error(errorMessage);
    }
}


/**
 * Tests the connection to the local LM Studio server.
 * @returns A promise that resolves to an object indicating success and a message.
 */
export async function testLocalConnection(): Promise<{ success: boolean; message: string; }> {
    return localConnector.testConnection();
}